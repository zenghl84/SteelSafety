// Demonstration parameters are separate from measured stress scores and device state.
(()=>{
const bundle=payload.key_indicators;if(!bundle)return;
const storageKey='steel-platform.key-indicators-mode.'+bundle.version;
let mode=bundle.default_mode;
try{const saved=localStorage.getItem(storageKey);if(['observed','demo'].includes(saved))mode=saved}catch(e){}
let sourceKey=window.stressAssessment?.getState().sourceKey||'confirmed';
const kindText={computed:'现有数据计算',demo:'演示参数 · 非实测',missing:'缺少项目数据'};
const format=p=>p.value===null?'待评估':Number(p.value).toFixed(p.precision);
function current(){return bundle.by_source[sourceKey][mode]}
function text(parent,tag,value,className){const el=document.createElement(tag);el.textContent=value;if(className)el.className=className;parent.append(el);return el}
function render(){
  const rows=current(),demoCount=rows.filter(p=>p.kind==='demo').length;
  for(const id of ['key-indicator-mode','key-indicator-mode-detail'])$(id).value=mode;
  $('key-mode-badge').textContent=demoCount?'含 '+demoCount+' 项演示':'现有数据';
  $('key-mode-badge').dataset.kind=demoCount?'demo':'computed';
  $('key-indicator-mode-note').textContent=demoCount?
    '演示参数模式：挠度、疲劳、腐蚀和寿命采用下方场景假设；应力比及复核项仍按当前评分源计算。演示项不参与 82.4 分计算。':
    '现有数据模式：只显示有项目依据的计算；缺少位移、疲劳谱、腐蚀检测和寿命评估的指标显示“待评估”。';
  $('key-indicator-mode-note').dataset.kind=demoCount?'demo':'computed';
  $('key-indicator-source-label').textContent=(sourceKey==='confirmed'?'已确认评分表':'最新监测记录')+' · '+(demoCount?'含演示参数':'现有数据');
  for(const p of rows){
    const card=document.querySelector('[data-key-indicator="'+p.id+'"]'),value=$('key-value-'+p.id),badge=$('key-badge-'+p.id);
    value.replaceChildren(document.createTextNode(format(p)));
    if(p.value!==null&&p.unit)text(value,'small',' '+p.unit);
    card.dataset.kind=p.kind;card.dataset.tone=p.tone;
    badge.textContent=p.badge;badge.className='pill '+(p.kind==='demo'?'key-demo-pill':p.kind==='missing'?'key-missing-pill':p.tone==='normal'?'green':'amber');
    card.title=kindText[p.kind]+'｜'+p.source+'\n'+p.calculation+'\n'+p.note;
    card.setAttribute('aria-label',p.label+' '+format(p)+(p.value!==null?p.unit:'')+'，'+kindText[p.kind]+'，点击查看'+(p.id==='risk'?'风险详情':'来源'));
    card.querySelector('.key-source-link').textContent=p.id==='risk'?'风险详情 ›':'来源 ›';
  }
  $('key-indicator-source-cards').replaceChildren(...rows.map(p=>{
    const article=document.createElement('article');article.className='key-source-card';article.id='key-source-'+p.id;article.tabIndex=-1;article.dataset.kind=p.kind;
    const head=text(article,'div','','key-source-head');
    text(head,'h4',p.label);
    text(head,'span',kindText[p.kind],'key-source-kind');
    text(article,'strong',format(p)+(p.value!==null&&p.unit?' '+p.unit:''),'key-source-value');
    text(article,'p','数值来源：'+p.source);
    text(article,'p','计算：'+(p.calculation||'缺少所需数据，未计算。'));
    if(p.note)text(article,'p',p.note,'key-source-note');
    if(p.risk_items?.length){const list=document.createElement('ul');p.risk_items.forEach(item=>text(list,'li',item.sensor_id+' · '+item.type+' · '+item.detail));article.append(list)}
    if(p.required)text(article,'p','正式接入需：'+p.required,'key-source-required');
    for(const ref of p.references){
      const line=text(article,'p','','key-source-reference'),link=document.createElement('a');
      link.href=ref.url;link.target='_blank';link.rel='noopener';link.textContent=ref.title+' ↗';line.append(link);
      text(line,'small',ref.role);
    }
    return article;
  }));
}
function setMode(next){
  if(!['observed','demo'].includes(next))return;
  mode=next;try{localStorage.setItem(storageKey,mode)}catch(e){}render();
}
function openSources(id){
  if(id==='risk'&&window.warningCenter){window.warningCenter.open();return}
  location.hash='assessment';showPage('assessment');
  requestAnimationFrame(()=>{
    const panel=$('assessment-workspace'),el=id?$('key-source-'+id):$('key-indicator-sources');
    const scale=dashboardScale||1;
    panel.scrollTop+=((el.getBoundingClientRect().top-panel.getBoundingClientRect().top)/scale)-12;
    el.focus({preventScroll:true});
    window.scrollTo(0,0);
  });
}
function exportSources(){
  const rows=current(),lines=['# 关键指标设置与来源','', $('key-indicator-source-label').textContent,'', $('key-indicator-mode-note').textContent,''];
  for(const p of rows){
    lines.push('## '+p.label+'：'+format(p)+(p.value!==null?p.unit:''),'','- 类型：'+kindText[p.kind],'- 数值来源：'+p.source,'- 计算：'+(p.calculation||'缺少数据，未计算。'),'- 说明：'+p.note);
    if(p.required)lines.push('- 正式接入需：'+p.required);
    for(const item of p.risk_items||[])lines.push('- 复核项：'+item.sensor_id+' · '+item.type+' · '+item.detail);
    for(const ref of p.references)lines.push('- 参考方法/原则：['+ref.title+']('+ref.url+')。'+ref.role);
    lines.push('');
  }
  const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/markdown;charset=utf-8'})),a=document.createElement('a');
  a.href=url;a.download='关键指标来源-'+(mode==='demo'?'含演示参数':'现有数据')+'.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
$('key-indicator-mode').onchange=e=>setMode(e.target.value);
$('key-indicator-mode-detail').onchange=e=>setMode(e.target.value);
$('key-indicator-more').onclick=()=>openSources();
$('key-indicator-export').onclick=exportSources;
document.querySelectorAll('[data-key-indicator]').forEach(card=>{
  card.onclick=()=>openSources(card.dataset.keyIndicator);
  card.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openSources(card.dataset.keyIndicator)}};
});
document.addEventListener('assessment-changed',e=>{sourceKey=e.detail.sourceKey;render()});
window.keyIndicators={getState:()=>({mode,sourceKey,indicators:current()}),setMode,exportSources};
render();
})();
