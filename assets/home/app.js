// Fit the dashboard when the window or browser fullscreen viewport changes.
let dashboardScale=1;
function fitDashboard(){
    dashboardScale=Math.min(window.innerWidth/1672,window.innerHeight/941);
    document.documentElement.style.setProperty('--dashboard-scale',String(dashboardScale));
}
fitDashboard();
window.addEventListener('resize',fitDashboard);
document.addEventListener('fullscreenchange',()=>requestAnimationFrame(fitDashboard));
window.visualViewport?.addEventListener('resize',fitDashboard);
const payload=JSON.parse(document.getElementById('payload').textContent),$=id=>document.getElementById(id);
$('model-frame').srcdoc=payload.viewer;
const ids=Array.from({length:10},(_,i)=>'S'+(i+1));$('sensor').innerHTML=ids.map(id=>`<option value="${id}" ${payload.history[id]?.length?'':'disabled'}>${id}测点 - ${payload.history[id]?.length?'应变':'无数据'}</option>`).join('');
const types=['局部屈曲','焊缝缺陷','腐蚀损伤','位移异常','应力异常'];$('damage-rows').innerHTML=types.map((t,i)=>`<tr><td>—</td><td>${['主梁','屋面支撑','纵向桁架','支座','钢柱'][i]}位置预留</td><td>${t}</td><td>—</td><td>待接入</td><td><button data-slot="损伤详情">查看</button></td></tr>`).join('');
let timer;function toast(text){$('toast').textContent=text;$('toast').style.display='block';clearTimeout(timer);timer=setTimeout(()=>$('toast').style.display='none',2800)}
function view(action,value){$('model-frame').contentWindow.postMessage({type:'platform-view',action,value},'*')}
document.querySelectorAll('[data-slot]').forEach(b=>b.onclick=()=>toast(b.dataset.slot+'：已预留位置，后续接入。'));
let riskValues=payload.stress_values||{};
$('risk-legend').title='CS19 · 合计 · 最后一步；色带在0/7.7/14.7/26.3/46.1/203 MPa锚点间连续插值，杆件按I/J端应力颜色沿长度插值。端间为显示插值，非新增计算截面。红色不代表超限，灰色为无结果。';
function setRisk(enabled){$('risk').checked=enabled;$('risk-legend').hidden=!enabled;$('model-frame').contentWindow.postMessage({type:'platform-view',action:'risk',value:enabled,values:riskValues},'*')}
$('risk').onchange=e=>setRisk(e.target.checked);
document.querySelector('.tabs button:first-child').onclick=()=>selectTool('rotate');
$('transparent').onchange=e=>view('transparent',e.target.checked);
function selectTool(mode){document.querySelector('.tabs button:first-child').classList.toggle('selected',mode!=='select');$('member-tab').classList.toggle('selected',mode==='select');document.querySelectorAll('[data-tool]').forEach(b=>b.classList.toggle('active',b.dataset.tool===mode));const clip=mode==='clip';$('clip-controls').hidden=!clip;$('member-controls').hidden=mode!=='select';if(clip){view('tool','select');sendClip(true)}else{sendClip(false);view('tool',mode)}toast({rotate:'旋转模式：左键拖动旋转模型。',pan:'平移模式：左键拖动平移模型。',zoom:'缩放模式：左键上下拖动，或滚轮缩放。',clip:'剖切已开启，使用滑块调整剖切位置。',select:'构件选择：可点击钢管构件，或按单元编号选择。',hide:'隐藏模式：点击构件隐藏；重置可恢复。'}[mode])}
function sendClip(enabled){$('model-frame').contentWindow.postMessage({type:'platform-view',action:'clip',value:enabled,axis:$('clip-axis').value,position:Number($('clip-position').value)},'*')}
document.querySelectorAll('[data-tool]').forEach(b=>b.onclick=()=>selectTool(b.dataset.tool));
$('select-member').onclick=()=>{const id=Number($('member-id').value);if(!Number.isSafeInteger(id)||id<1){toast('请输入有效单元编号。');return}view('select-id',id)};
$('member-id').onkeydown=e=>{if(e.key==='Enter')$('select-member').click()};
$('hide-selected').onclick=()=>view('hide-selected');$('close-member').onclick=()=>selectTool('rotate');
$('clip-position').oninput=()=>sendClip(true);$('clip-axis').onchange=()=>sendClip(true);
$('close-clip').onclick=()=>{sendClip(false);selectTool('rotate')};
$('member-tab').onclick=()=>selectTool('select');
document.querySelector('[data-tool="rotate"]').classList.add('active');
window.addEventListener('message',e=>{if(e.source!==$('model-frame').contentWindow)return;if(e.data?.type==='platform-notice')toast(e.data.text);if(e.data?.type==='platform-reset'){$('clip-controls').hidden=true;$('member-controls').hidden=true;document.querySelectorAll('[data-tool]').forEach(b=>b.classList.toggle('active',b.dataset.tool==='rotate'))}});
$('reset').onclick=()=>view('reset');$('sensors').onchange=e=>view('sensors',e.target.checked);
$('live-data').onclick=()=>toast(`${payload.source}，最新 ${payload.latest.replace('T',' ')}；${Object.keys(payload.history).length}/10测点，S4缺失。曲线显示表格应变变化值，不是实时采集。`);
$('export').onclick=()=>{if(window.stressAssessment)window.stressAssessment.exportSummary();else toast('评估数据尚未就绪。')};
function clock(){$('clock').textContent=new Date().toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}).replaceAll('/','-')}
function chart(id,records,opt={}){const c=$(id),ctx=c.getContext('2d'),w=c.width,h=c.height,l=44,r=7,t=12,b=27;ctx.clearRect(0,0,w,h);ctx.font='10px Microsoft YaHei';const valid=records.filter(x=>x.value!==null&&Number.isFinite(x.value));if(!valid.length){ctx.fillStyle='#8b9bab';ctx.fillText('该测点暂无数据',w/2-48,h/2);return}let min=opt.min??Math.min(...valid.map(x=>x.value)),max=opt.max??Math.max(...valid.map(x=>x.value));if(max===min){min-=1;max+=1}if(opt.min===undefined){const p=(max-min)*.18;min-=p;max+=p}for(let i=0;i<5;i++){const y=t+(h-t-b)*i/4;ctx.strokeStyle='#e7edf3';ctx.beginPath();ctx.moveTo(l,y);ctx.lineTo(w-r,y);ctx.stroke();ctx.fillStyle='#6e7a87';ctx.fillText(String(Math.round(max-(max-min)*i/4)),7,y+3)}const start=Date.parse(records[0].timestamp),end=Date.parse(records.at(-1).timestamp),xy=x=>[l+(w-l-r)*(end===start?.5:(Date.parse(x.timestamp)-start)/(end-start)),t+(h-t-b)*(max-x.value)/(max-min)];ctx.strokeStyle='#2983bf';ctx.lineWidth=1.2;ctx.beginPath();let connected=false;records.forEach(x=>{if(x.value===null||!Number.isFinite(x.value)){connected=false;return}const p=xy(x);connected?ctx.lineTo(...p):ctx.moveTo(...p);connected=true});ctx.stroke();if(opt.fill){ctx.lineTo(xy(valid.at(-1))[0],h-b);ctx.lineTo(xy(valid[0])[0],h-b);ctx.closePath();ctx.fillStyle='#51a9d92b';ctx.fill()}if(Number.isFinite(opt.reference)){const y=t+(h-t-b)*(max-opt.reference)/(max-min);ctx.save();ctx.strokeStyle='#cc7990';ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(l,y);ctx.lineTo(w-r,y);ctx.stroke();ctx.restore()}ctx.fillStyle='#73818d';for(let i=0;i<6;i++){const d=new Date(start+(end-start)*i/5),label=end-start<=864e5?d.toLocaleTimeString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}).slice(0,5):d.toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'}).slice(5);ctx.textAlign=i===0?'left':i===5?'right':'center';ctx.fillText(label,l+(w-l-r)*i/5,h-9)}ctx.textAlign='left'}
let strainRows=[];
function strain(){
    let rows=payload.history[$('sensor').value]||[];
    if(rows.length&&$('period').value!=='all'){
        const from=Date.parse(rows.at(-1).timestamp)-Number($('period').value)*864e5;
        rows=rows.filter(x=>Date.parse(x.timestamp)>=from);
    }
    strainRows=rows;
    if(window.windReady)resetWind();
    chart('strain-chart',rows);
    const valid=rows.filter(r=>r.value!==null&&Number.isFinite(r.value));
    const format=t=>new Date(t).toLocaleString('sv-SE',{timeZone:'Asia/Shanghai',hour12:false}).slice(0,16);
    $('strain-summary').textContent=rows.length?`${format(rows[0].timestamp)} ～ ${format(rows.at(-1).timestamp)} · ${valid.length}条有效值`:'该测点暂无数据';
    $('strain-summary').title=payload.source+'｜应变变化值（με）｜'+$('strain-summary').textContent;
}
$('strain-chart').onmousemove=e=>{
    const c=e.currentTarget,r=c.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*c.width;
    if(!strainRows.length)return;
    const start=Date.parse(strainRows[0].timestamp),end=Date.parse(strainRows.at(-1).timestamp);
    const time=start+Math.max(0,Math.min(1,(x-44)/(c.width-51)))*(end-start);
    const row=strainRows.reduce((a,b)=>Math.abs(Date.parse(a.timestamp)-time)<=Math.abs(Date.parse(b.timestamp)-time)?a:b);
    c.title=`${$('sensor').value}｜${new Date(row.timestamp).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}｜${row.value===null?'缺失':row.value+' με'}`;
};
$('sensor').onchange=strain;$('period').onchange=strain;
function health(){const c=$('health-chart'),ctx=c.getContext('2d');ctx.font='10px Microsoft YaHei';for(let i=0;i<5;i++){const y=18+i*23;ctx.strokeStyle='#edf2f6';ctx.beginPath();ctx.moveTo(38,y);ctx.lineTo(268,y);ctx.stroke();ctx.fillStyle='#8a97a4';ctx.fillText(String(200-i*50),5,y+3)}const colors=['#6ac38e','#68b6de','#e5bb68','#e59b79'],heights=[72,26,11,4];['完好','轻微损伤','中等损伤','严重损伤'].forEach((name,i)=>{const x=48+i*56,y=110-heights[i];ctx.fillStyle=colors[i];ctx.fillRect(x,y,29,heights[i]);ctx.fillStyle='#8897a5';ctx.textAlign='center';ctx.fillText('—',x+14,y-7);ctx.fillText(name,x+14,128);ctx.textAlign='left'})}
clock();strain();health();setInterval(clock,1000);
const ring=document.querySelector('.donut svg');let offset=0;['#927dcc','#46bcea','#f3d779','#67c890','#4bbba8'].forEach((color,i)=>{const size=[86,58,49,65,44][i],part=document.createElementNS('http://www.w3.org/2000/svg','circle');for(const [key,value] of Object.entries({cx:66,cy:66,r:48,fill:'none',stroke:color,'stroke-width':25,'stroke-dasharray':`${size} 302`,'stroke-dashoffset':-offset,transform:'rotate(-90 66 66)'}))part.setAttribute(key,value);ring.appendChild(part);offset+=size});
window.platform={getLayout:()=>({width:1672,height:941,scale:dashboardScale,viewportWidth:window.innerWidth,viewportHeight:window.innerHeight,mode:'fit-viewport'}),selectSensor:id=>{if(ids.includes(id)){$('sensor').value=id;strain()}}};
window.platform.setRiskValues=values=>{riskValues=Object.fromEntries(Object.entries(values||{}).filter(([id,v])=>/^\d+$/.test(id)&&typeof v==='number'&&Number.isFinite(v)&&v>=0));setRisk($('risk').checked)};

// Project metadata stays separate from monitoring measurements and the Gen model.
const projectKeys=['project_name','structure_type','building_use','location','span','height','material','built_date','service_years'];
const infoValues=Array.from(document.querySelectorAll('.project-info dd')),infoLabels=Array.from(document.querySelectorAll('.project-info dt'));
const projectDefaults=Object.fromEntries(projectKeys.map((key,i)=>[key,infoValues[i].textContent]));
let projectInfo={...projectDefaults};const storageKey='steel-platform.project-info.v1';
try{const saved=JSON.parse(localStorage.getItem(storageKey)||'null');if(saved&&typeof saved==='object')projectKeys.forEach(key=>{if(typeof saved[key]==='string'&&saved[key].length<=80)projectInfo[key]=saved[key]})}catch(e){}
function applyProject(){projectKeys.forEach((key,i)=>{infoValues[i].textContent=projectInfo[key]||'待填写';infoValues[i].title=projectInfo[key]||'待填写'});document.querySelector('.project b').textContent=(projectInfo.project_name||projectDefaults.project_name)+'⌄'}
applyProject();
projectKeys.forEach((key,i)=>{const label=document.createElement('label'),text=document.createElement('span'),input=document.createElement('input');text.textContent=infoLabels[i].textContent;input.name=key;input.id='project-'+key;input.maxLength=80;input.required=i===0;label.append(text,input);$('project-fields').appendChild(label)});
$('edit-project').onclick=()=>{projectKeys.forEach(key=>$('project-'+key).value=projectInfo[key]);$('project-dialog').showModal()};
$('project-cancel').onclick=()=>$('project-dialog').close();
$('project-form').onsubmit=e=>{e.preventDefault();const next=Object.fromEntries(projectKeys.map(key=>[key,$('project-'+key).value.trim()]));if(!next.project_name){toast('项目名称不能为空。');return}try{localStorage.setItem(storageKey,JSON.stringify(next));projectInfo=next;applyProject();$('project-dialog').close();toast('项目基本信息已保存到本机浏览器。')}catch(err){toast('浏览器未允许保存，请先导出项目配置备份。')}};
$('project-export').onclick=()=>{const values=Object.fromEntries(projectKeys.map(key=>[key,$('project-'+key).value.trim()])),a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(values,null,2)],{type:'application/json;charset=utf-8'}));a.href=url;a.download='项目基本信息.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};

// Keep the homepage mounted so model state and chart selections survive navigation.
const pageButtons=Array.from(document.querySelectorAll('nav [data-page]'));
function showPage(key){
    const button=pageButtons.find(b=>b.dataset.page===key)||pageButtons[0];
    const home=button.dataset.page==='home';
    $('home-page').hidden=!home;
    $('module-page').hidden=home;
    $('wind-settings').hidden=button.dataset.page!=='settings';
    $('module-title').textContent=Array.from(button.childNodes).filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join('').trim();
    pageButtons.forEach(b=>{const active=b===button;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});
    clearTimeout(timer);$('toast').style.display='none';
    if(!home)$('module-title').focus({preventScroll:true});
}
pageButtons.forEach(b=>b.onclick=()=>{location.hash=b.dataset.page});
$('back-home').onclick=()=>{location.hash='home'};
window.addEventListener('hashchange',()=>showPage(location.hash.slice(1)));
showPage(location.hash.slice(1)||'home');

const windDefaults={mean:2.3,amplitude:1.4,gust:3,reference:5,interval:1,step:1,seed:42,loop:true};
const windStorageKey='steel-platform.wind-settings.v1';
function validateWind(c){
    const ranges={mean:[0,20],amplitude:[0,10],gust:[0,15],reference:[.1,40],interval:[.2,60],step:[1,24],seed:[1,999999]};
    return c&&Object.entries(ranges).every(([k,[a,b]])=>typeof c[k]==='number'&&Number.isFinite(c[k])&&c[k]>=a&&c[k]<=b)&&Number.isInteger(c.step)&&Number.isInteger(c.seed)&&typeof c.loop==='boolean';
}
let windConfig={...windDefaults};
try{const saved=JSON.parse(localStorage.getItem(windStorageKey)||'null');if(validateWind(saved))windConfig=saved}catch(e){}
let windAll=[],windRows=[],windCursor=0,windTimer=null,windPlaying=true;
const windForm=$('wind-settings-form');
function fillWindForm(){for(const k of Object.keys(windDefaults)){const input=windForm.elements.namedItem(k);if(k==='loop')input.checked=windConfig[k];else input.value=windConfig[k]}}
function windValue(timestamp){
    const hour=Date.parse(timestamp)/36e5,seed=windConfig.seed;
    // Continuous time signals make the same timestamp reproduce the same value.
    const day=2*Math.PI*(hour%24)/24;
    const wave=.45*Math.sin(day-1.2)+.3*Math.sin(hour*.18+seed)+.25*Math.sin(hour*1.71+seed*.31);
    const burst=Math.pow(Math.max(0,Math.sin(hour*.093+seed*.13)),16);
    return Number(Math.max(0,windConfig.mean+windConfig.amplitude*wave+windConfig.gust*burst).toFixed(3));
}
function windTime(t){return new Date(t).toLocaleString('sv-SE',{timeZone:'Asia/Shanghai',hour12:false}).slice(0,16)}
function drawWind(){
    windRows=windAll.slice(0,windCursor);
    const max=Math.ceil(Math.max(6,windConfig.reference*1.15,...windAll.map(r=>r.value*1.15))/2)*2;
    chart('wind-chart',windRows,{min:0,max,fill:true,reference:windConfig.reference});
    $('wind-reference-label').textContent=`参考线 ${windConfig.reference} m/s`;
    const latest=windRows.at(-1);
    $('wind-summary').textContent=latest?`${windTime(latest.timestamp)} · ${latest.value.toFixed(2)} m/s · ${windCursor}/${windAll.length}`:'暂无时间节点';
    $('wind-playback-status').textContent=latest?`${windPlaying?'播放中':'已暂停'} · ${$('sensor').value} 时间轴 · ${windTime(latest.timestamp)} · 已显示 ${windCursor} / ${windAll.length} 个节点`:'暂无时间节点';
    for(const id of ['wind-toggle','settings-wind-toggle'])$(id).textContent=windPlaying?'暂停':'继续';
    $('wind-progress').max=String(Math.max(1,windAll.length));$('wind-progress').value=String(windCursor);
}
function scheduleWind(){
    clearInterval(windTimer);windTimer=null;
    if(!windPlaying||windAll.length<2)return;
    windTimer=setInterval(()=>{
        if(windCursor>=windAll.length){if(windConfig.loop)windCursor=1;else{windPlaying=false;scheduleWind();drawWind();return}}
        else windCursor=Math.min(windAll.length,windCursor+windConfig.step);
        drawWind();
    },windConfig.interval*1000);
}
function resetWind(){
    windAll=strainRows.map(r=>({timestamp:r.timestamp,value:windValue(r.timestamp)}));
    windCursor=Math.min(24,windAll.length);$('wind-period').value=$('period').value;
    drawWind();scheduleWind();
}
function toggleWind(){if(!windPlaying&&windCursor===windAll.length)windCursor=Math.min(2,windAll.length);windPlaying=!windPlaying;drawWind();scheduleWind()}
function restartWind(){windCursor=Math.min(2,windAll.length);windPlaying=true;drawWind();scheduleWind()}
$('wind-toggle').onclick=toggleWind;$('settings-wind-toggle').onclick=toggleWind;
$('wind-restart').onclick=restartWind;$('settings-wind-restart').onclick=restartWind;
$('wind-period').onchange=()=>{$('period').value=$('wind-period').value;strain()};
$('wind-progress').oninput=e=>{windPlaying=false;windCursor=Number(e.target.value);drawWind();scheduleWind()};
windForm.onsubmit=e=>{
    e.preventDefault();const next=Object.fromEntries(Object.keys(windDefaults).map(k=>[k,k==='loop'?windForm.elements.namedItem(k).checked:Number(windForm.elements.namedItem(k).value)]));
    if(!validateWind(next)){$('wind-save-status').textContent='请检查输入范围。';return}
    windConfig=next;let saved=true;try{localStorage.setItem(windStorageKey,JSON.stringify(next))}catch(e){saved=false}
    resetWind();$('wind-save-status').textContent=saved?'已保存并应用':'已应用，本浏览器未允许保存设置';
};
$('wind-defaults').onclick=()=>{windConfig={...windDefaults};fillWindForm();try{localStorage.removeItem(windStorageKey)}catch(e){}resetWind();$('wind-save-status').textContent='已恢复默认参数'};
$('wind-chart').onmousemove=e=>{
    if(!windRows.length)return;const c=e.currentTarget,r=c.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*c.width;
    const time=Date.parse(windRows[0].timestamp)+Math.max(0,Math.min(1,(x-44)/(c.width-51)))*(Date.parse(windRows.at(-1).timestamp)-Date.parse(windRows[0].timestamp));
    const row=windRows.reduce((a,b)=>Math.abs(Date.parse(a.timestamp)-time)<=Math.abs(Date.parse(b.timestamp)-time)?a:b);
    c.title=`${windTime(row.timestamp)}｜${row.value.toFixed(3)} m/s`;
};
fillWindForm();window.windReady=true;resetWind();

