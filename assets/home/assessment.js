// All numerical results come from core/assessment.py; both views share this state.
(()=>{
const config=payload.assessment,root=$('assessment-workspace');
if(!config||!root)return;
const sourceSelect=$('assessment-source');
let sourceKey=config.default_source;
const sourceStorageKey='steel-platform.assessment-source.v1.8.'+config.version;
try{const saved=localStorage.getItem(sourceStorageKey);if(config.snapshots[saved])sourceKey=saved}catch(e){}
const number=(v,d=1)=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(d):'—';
const percent=v=>typeof v==='number'&&Number.isFinite(v)?(100*v).toFixed(2)+'%':'—';
const snapshot=()=>config.snapshots[sourceKey];
function cell(row,text,className){const td=document.createElement('td');td.textContent=text;if(className)td.className=className;row.append(td);return td}
function currentNotice(data){
  const s=data.summary,parts=[];
  if(s.fault_count)parts.push(s.fault_sensor_ids.join('、')+' 已由用户标记为传感器损坏，保留原读数，剔除有效测点统计。');
  if(s.reference_mean_includes_faults)parts.push('平均参考分 '+number(s.mean_score)+' 沿用 '+s.reference_score_count+' 点原映射（含故障点原映射值）；有效点均分 '+number(s.valid_mean_score)+'。');
  if(s.over_limit_count)parts.push(s.over_limit_count+' 个测点换算值达到或超过材料基准，需核查监测系统与结构实际状态。');
  if(s.missing_count)parts.push(s.missing_count+' 个测点缺少有效数据，控制分暂不发布。');
  if(!parts.length)parts.push(s.status+'；结合对应构件的稳定性与正式监测限值复核。');
  return parts.join(' ');
}
function render(){
  const data=snapshot(),s=data.summary;
  sourceSelect.value=sourceKey;
  $('overall-assessment').dataset.tone=s.tone;
  $('overall-status').textContent=s.status;
  $('overall-control').textContent=(s.fault_count?s.fault_sensor_ids.join('、')+' 损坏':'最低分 '+(s.control_sensor_ids.join('、')||'—'))+' · '+s.valid_count+'/'+s.expected_count+' 有效';
  $('overall-control').title=$('overall-control').textContent;
  $('overall-source').textContent=data.label+(s.reference_mean_includes_faults?' · 含S1原映射':' · 原映射均分');
  $('overall-source').title=currentNotice(data);
  $('overall-score').textContent=number(s.mean_score);
  $('overall-icon').textContent=s.tone==='normal'?'✓':'!';
  $('overall-score-arc').setAttribute('stroke-dasharray',s.mean_score===null?'0 327':(327*s.mean_score/100)+' 327');
  $('overall-assessment').setAttribute('aria-label','总体安全评估：'+s.status+'，平均参考分 '+number(s.mean_score)+'，来源 '+data.label);
  $('overall-assessment').title=data.label+'；'+data.time_label+'；'+currentNotice(data);
  $('assessment-reference-card').dataset.tone=s.tone;
  $('assessment-mean-score').textContent=number(s.mean_score);
  $('assessment-mean-basis').textContent=s.reference_score_count+' 点原映射'+(s.reference_mean_includes_faults?'，含故障点原值':'');
  $('assessment-valid-mean-score').textContent=number(s.valid_mean_score);
  $('assessment-coverage').textContent=s.valid_count+' / '+s.expected_count;
  $('assessment-coverage-note').textContent=[s.fault_count?s.fault_count+' 点传感器损坏':'',s.missing_count?s.missing_count+' 点缺测':'','S4 未纳入'].filter(Boolean).join(' · ');
  $('assessment-fault-sensors').textContent=s.fault_sensor_ids.join('、')||'无';
  $('assessment-status').textContent=s.status;
  $('assessment-notice').dataset.tone=s.tone;
  $('assessment-notice').textContent=currentNotice(data);
  $('assessment-data-caption').textContent=data.label+' · '+data.time_label;
  $('assessment-rows').replaceChildren(...data.rows.map(p=>{
    const tr=document.createElement('tr');tr.dataset.sensor=p.sensor_id;tr.dataset.tone=p.tone;tr.title=p.reason||p.component;
    const first=cell(tr,p.sensor_id,'sa-sensor');
    const sub=document.createElement('small');sub.textContent=p.component;first.append(sub);
    cell(tr,'E'+p.element+' / '+p.end);
    cell(tr,p.material);
    cell(tr,number(p.initial_mpa,4));
    cell(tr,number(p.delta_mpa,4));
    cell(tr,number(p.total_mpa,4),'sa-total');
    cell(tr,number(p.reference_mpa,0));
    cell(tr,percent(p.ratio));
    const td=cell(tr,'','sa-point-score'),bar=document.createElement('i'),value=document.createElement('b');
    bar.style.setProperty('--point-score',p.score===null?'0%':Math.max(0,Math.min(100,p.score))+'%');value.textContent=number(p.score);td.append(value,bar);
    if(p.tone==='fault'){const original=document.createElement('small');original.textContent='原映射 '+number(p.reference_score);td.append(original)}
    const last=cell(tr,''),badge=document.createElement('span');badge.className='sa-badge';badge.dataset.tone=p.tone;badge.textContent=p.status;last.append(badge);
    if(sourceKey==='monitoring'){const time=document.createElement('small');time.className='sa-record-time';time.textContent=p.timestamp?p.timestamp.replace('T',' '):'无监测记录';last.append(time)}
    return tr;
  }));
  $('assessment-time-note').textContent=sourceKey==='confirmed'?
    '来源为用户确认表格，原表未提供采样时刻；此处保留该表快照，不与当前工作簿记录混算。':
    '按各测点最新记录计算：实测增量 = 温补后应变(με) × 0.206。温补沿用原表公式；各点采样时间见状态列，不插值、不复用较早的有效值。';
  document.dispatchEvent(new CustomEvent('assessment-changed',{detail:{sourceKey}}));
}
function download(name,text,type){
  const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');
  a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function exportTable(){
  const data=snapshot(),headers=['数据来源','采样时刻','测点','单元','端面','应力分量','钢材','CS18初始应力(MPa)','实测增量(MPa)','估计总应力(MPa)','材料基准(MPa)','占用比','有效评分','原映射参考分','状态','设备状态记录来源','说明'];
  const rows=[headers,...data.rows.map(p=>[data.label,p.timestamp||'原表未提供',p.sensor_id,p.element,p.end,p.component,p.material,p.initial_mpa,p.delta_mpa??'',p.total_mpa??'',p.reference_mpa,p.ratio??'',p.score??'',p.reference_score??'',p.status,p.status_reported_by||'',p.reason])];
  const csv='\ufeff'+rows.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');
  download('应力评分计算表-'+data.label+'.csv',csv,'text/csv;charset=utf-8');
}
function exportSummary(){
  const data=snapshot(),s=data.summary;
  const text=['钢结构应力评分摘要','数据来源：'+data.label,'采样时间：'+data.time_label,'安装基准：CS18','首页平均参考分（原映射口径）：'+number(s.mean_score),'有效测点均分：'+number(s.valid_mean_score),'故障测点：'+(s.fault_sensor_ids.join('、')||'无'),'状态：'+s.status,'有效评分覆盖：'+s.valid_count+'/'+s.expected_count,'统计说明：'+currentNotice(data),'规则：r=|CS18初值+实测增量|/材料基准；50%/70%/90%/100%分别映射100/80/60/0分，分段线性插值。','本页为材料应力参考评分，分数映射为项目规则。'].join('\r\n');
  download('安全评估摘要.txt','\ufeff'+text,'text/plain;charset=utf-8');
}
function setSource(next){if(!config.snapshots[next])return;sourceKey=next;try{localStorage.setItem(sourceStorageKey,sourceKey)}catch(e){}render()}
sourceSelect.onchange=()=>setSource(sourceSelect.value);
$('assessment-export').onclick=exportTable;
$('overall-assessment-details').onclick=()=>{location.hash='assessment';showPage('assessment')};
const previousShow=showPage;
showPage=function(key){previousShow(key);root.hidden=key!=='assessment'};
window.addEventListener('hashchange',()=>showPage(location.hash.slice(1)));
window.stressAssessment={getState:()=>({sourceKey,...snapshot()}),setSource,exportTable,exportSummary};
render();showPage(location.hash.slice(1)||'home');
})();
