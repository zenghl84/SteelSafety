// The warning center and homepage use the same assessment source and risk set.
(()=>{
const bundle=payload.alerts,root=$('alerts-workspace');if(!bundle||!root)return;
let sourceKey=window.stressAssessment.getState().sourceKey,selectedId=null,filter='all';
const current=()=>bundle.snapshots[sourceKey];
const number=(v,d=4)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(d):'—';
function el(parent,tag,value,cls){const n=document.createElement(tag);if(value!==undefined)n.textContent=value;if(cls)n.className=cls;parent.append(n);return n}
function button(parent,label,handler,cls){const b=el(parent,'button',label,cls);b.type='button';b.onclick=handler;return b}
function go(key){location.hash=key;showPage(key);window.scrollTo(0,0)}
function locate(item){go('home');window.platform.selectSensor(item.sensor_id);view('select-id',item.element);toast(item.sensor_id+' · 单元 E'+item.element+' / '+item.end+' 端')}
function calculations(item){
  go('assessment');
  requestAnimationFrame(()=>{
    const panel=$('assessment-workspace'),row=document.querySelector('#assessment-rows tr[data-sensor="'+item.sensor_id+'"]');
    panel.scrollTop+=((row.getBoundingClientRect().top-panel.getBoundingClientRect().top)/(dashboardScale||1))-100;
    row.classList.remove('aw-highlight');void row.offsetWidth;row.classList.add('aw-highlight');
    window.scrollTo(0,0);
  });
}
function history(item){go('monitoring');window.monitoringWorkbench.selectSensor(item.sensor_id);$('monitor-workspace').scrollTop=0}
function renderDetail(item){
  const panel=$('alerts-detail');panel.replaceChildren();
  if(!item){el(panel,'div','当前筛选没有待复核项。','aw-empty');return}
  panel.dataset.tone=item.tone;panel.dataset.sensor=item.sensor_id;
  const head=el(panel,'div',undefined,'aw-detail-heading'),heading=el(head,'div');
  el(heading,'small',item.sensor_id+' · E'+item.element+' / '+item.end+' 端 · '+item.material,'aw-location');
  el(heading,'h3',item.title);
  const status=el(head,'span',item.type+' · '+item.state,'aw-tag');status.dataset.tone=item.tone;
  el(panel,'p',item.component+' ｜ '+item.brief,'aw-brief');
  const metrics=el(panel,'div',undefined,'aw-detail-metrics');
  for(const m of item.metrics){const box=el(metrics,'div');el(box,'small',m.label);const v=el(box,'strong',m.value);el(v,'em',m.unit)}
  const body=el(panel,'div',undefined,'aw-detail-columns');
  const evidence=el(body,'div',undefined,'aw-evidence');el(evidence,'h4','触发依据');
  el(evidence,'p',item.trigger,'aw-trigger');el(evidence,'p',item.calculation,'aw-formula');
  if(item.thresholds){
    const ratio=item.row.ratio,scale=1.2,bar=el(evidence,'div',undefined,'aw-ratio-bar');
    bar.setAttribute('aria-label','材料应力比 '+(ratio*100).toFixed(2)+'%；关注70%，预警90%，材料基准100%');
    const track=el(bar,'div',undefined,'aw-ratio-track');
    const fill=el(track,'i');fill.style.width=Math.min(100,ratio*100/scale)+'%';
    for(const t of item.thresholds){const mark=el(track,'b');mark.style.left=(t.ratio*100/scale)+'%';mark.title=t.label+' '+(t.ratio*100).toFixed(0)+'%'}
    const marker=el(track,'span',ratio>1.2?'>120%':(100*ratio).toFixed(2)+'%');marker.style.left=Math.min(97,ratio*100/scale)+'%';
    const limits=el(bar,'div',undefined,'aw-thresholds');
    for(const t of item.thresholds){const b=el(limits,'div');el(b,'small',t.label+' '+Math.round(100*t.ratio)+'%');el(b,'b',number(t.mpa,1)+' MPa')}
    el(evidence,'small','材料应力比；70% / 90% 为项目暂定分界。','aw-rule-caption');
  }
  el(evidence,'p',item.impact,'aw-impact');
  const actions=el(body,'div',undefined,'aw-suggestions');el(actions,'h4','建议处置');
  const steps=el(actions,'ol');item.actions.forEach(a=>el(steps,'li',a));
  el(actions,'p','当前尚未录入检修或复核完成记录。','aw-unresolved');
  const provenance=el(panel,'div',undefined,'aw-provenance');
  const facts=[['数据来源',item.source_label+' · '+item.source],['采样时间',item.measurement_time.replace('T',' ')],['记录依据',item.record_by+(item.category==='equipment'?' · 标记日期 '+item.record_time:' · '+item.record_time)]];
  for(const [label,value] of facts){const line=el(provenance,'p');el(line,'b',label);el(line,'span',value)}
  el(provenance,'p',item.score_note,'aw-score-note');
  if(item.category==='equipment'){
    const raw=el(panel,'details',undefined,'aw-raw');el(raw,'summary','查看故障点原始留档（退出有效受力判断）');
    el(raw,'p','CS18 初值 '+number(item.row.initial_mpa)+' MPa；原实测增量 '+number(item.row.delta_mpa)+' MPa；原换算总值 '+number(item.row.total_mpa)+' MPa；原映射 '+number(item.row.reference_score,1)+' 分。');
    el(raw,'small','以上数据用于追溯；设备损坏状态下不据此判断对应构件是否超限。');
  }
  const footer=el(panel,'div',undefined,'aw-detail-footer'),refs=el(footer,'div',undefined,'aw-references');
  for(const r of item.references){const a=el(refs,'a',r.title+' ↗');a.href=r.url;a.target='_blank';a.rel='noopener';a.title=r.role}
  const controls=el(footer,'div',undefined,'aw-detail-actions');
  button(controls,'查看计算',()=>calculations(item));button(controls,'监测历史',()=>history(item));button(controls,'模型定位 ↗',()=>locate(item),'aw-primary');
}
function render(){
  const data=current(),items=data.items,visible=items.filter(i=>filter==='all'||i.category===filter);
  if(!visible.some(i=>i.id===selectedId))selectedId=visible[0]?.id||null;
  $('alerts-source').value=sourceKey;
  $('alerts-count').textContent=data.counts.total;
  $('alerts-equipment-count').textContent=data.counts.equipment;
  $('alerts-stress-count').textContent=data.counts.stress;
  $('alerts-coverage').textContent=data.valid_count+' / '+data.expected_count;
  $('alerts-coverage-note').textContent=data.counts.data?data.counts.data+' 点缺测 · S4 未纳入':'故障点退出有效统计 · S4 未纳入';
  $('alerts-snapshot-label').textContent=data.label;
  $('alerts-snapshot-time').textContent=data.time_label;
  $('alerts-note').textContent=data.note;
  $('alerts-filter-count').textContent=visible.length+' / '+items.length+' 项';
  const list=$('alerts-list');list.replaceChildren();
  document.querySelectorAll('[data-alert-filter]').forEach(b=>{const active=b.dataset.alertFilter===filter;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active))});
  for(const item of visible){
    const card=button(list,'',()=>{selectedId=item.id;render()},'aw-risk-card');card.dataset.sensor=item.sensor_id;card.dataset.tone=item.tone;
    card.classList.toggle('selected',item.id===selectedId);card.setAttribute('aria-pressed',String(item.id===selectedId));
    card.setAttribute('aria-label',item.sensor_id+' '+item.title+' '+item.state+'，查看详情');
    const top=el(card,'span',undefined,'aw-risk-top');el(top,'b',item.sensor_id,'aw-sensor');el(top,'span',item.priority,'aw-priority');el(top,'span','›','aw-chevron');
    el(card,'strong',item.title);el(card,'small','E'+item.element+' / '+item.end+' 端 · '+item.type);
    el(card,'p',item.brief);const bottom=el(card,'span',undefined,'aw-risk-bottom');el(bottom,'span',item.state);el(bottom,'small',item.category==='equipment'?'用户标记 · '+item.record_time:'应力比 '+(100*item.row.ratio).toFixed(2)+'%');
    if(item.category==='data')bottom.lastChild.textContent='无有效读数';
  }
  if(!visible.length)el(list,'p','当前筛选没有待复核项。','aw-empty');
  renderDetail(visible.find(i=>i.id===selectedId));
  document.querySelector('nav [data-page="alerts"] em').textContent=items.length;
  const bell=document.querySelector('.bell');bell.querySelector('sup').textContent=items.length;bell.setAttribute('aria-label','预警中心：'+items.length+' 项待复核');
  renderHome(items);
}
function renderHome(items){
  const rows=$('home-risk-rows');rows.replaceChildren();
  for(const item of items.slice(0,4)){
    const row=el(rows,'div');row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label','查看 '+item.sensor_id+' '+item.title);row.onclick=()=>open(item.id);row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open(item.id)}};
    el(row,'i',undefined,item.category==='stress'?'orange':'yellow');
    el(row,'span',item.category==='equipment'?'标记 '+item.record_time:item.row.timestamp?item.row.timestamp.replace('T',' ').slice(5,16):'采样时刻未提供');
    el(row,'p',item.sensor_id+' · '+item.title+' · E'+item.element+' / '+item.end);
    el(row,'em',item.state,'pill amber');
  }
  if(!items.length)el(rows,'p','当前快照未触发复核项。','aw-empty');
  $('home-risk-caption').textContent=current().label+' · '+items.length+' 项';
}
function open(sensorId){filter='all';selectedId=sensorId||current().items[0]?.id||null;render();go('alerts');root.scrollTop=0}
function exportDetails(){
  const data=current(),lines=['# 预警中心风险源详情','',data.label+' · '+data.time_label,'','待处理复核项：'+data.items.length,'',data.note,''];
  for(const item of data.items){
    lines.push('## '+item.sensor_id+' · '+item.title,'','- 位置：E'+item.element+' / '+item.end+' 端 · '+item.material+' · '+item.component,'- 类别/状态：'+item.type+' / '+item.state,'- 触发依据：'+item.trigger,'- 计算：'+item.calculation,'- 影响：'+item.impact,'- 数据来源：'+item.source_label+' · '+item.source,'- 采样时间：'+item.measurement_time,'- 记录依据：'+item.record_by+' · '+item.record_time,'- 评分口径：'+item.score_note,'');
    item.metrics.forEach(m=>lines.push('- '+m.label+'：'+m.value+' '+m.unit));
    lines.push('','建议处置：');item.actions.forEach((a,i)=>lines.push((i+1)+'. '+a));
    lines.push('');item.references.forEach(r=>lines.push('参考：['+r.title+']('+r.url+')。'+r.role));lines.push('');
  }
  const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/markdown;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='风险源详情-'+data.label+'.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
document.querySelectorAll('[data-alert-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.alertFilter;render()});
$('alerts-source').onchange=e=>window.stressAssessment.setSource(e.target.value);
$('alerts-export').onclick=exportDetails;
document.querySelector('.bell').onclick=()=>open();$('home-risk-more').onclick=()=>open();
document.addEventListener('assessment-changed',e=>{sourceKey=e.detail.sourceKey;render()});
const previousShow=showPage;showPage=function(key){previousShow(key);root.hidden=key!=='alerts'};
window.addEventListener('hashchange',()=>showPage(location.hash.slice(1)));
window.warningCenter={open,exportDetails,getState:()=>({sourceKey,filter,selectedId,...current()})};
render();showPage(location.hash.slice(1)||'home');
})();
