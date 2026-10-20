(()=>{
const root=$('knowledge-workspace');
const rules={title:'临时数据异常筛查规则 v2',code:'项目暂定 · 非规范安全限值',category:'项目规则',url:'/app/static/knowledge/临时预警规则.md',location:'应变：绝对值≥1000με重点提醒；温度：暂不设筛查阈值',summary:'应变绝对值≥1000με时独立触发重点提醒，不受滚动基线影响，需排查仪器、测点、零点与实际受力；不直接认定仪器故障。相对偏离仍采用±100/±300με。基线采用同测点此前24小时的中位数，至少12个有效值；相邻记录≤90分钟时另检查突跳。超过90分钟只标记记录间隔异常。保留原始值。正式结构预警需结合设计模型、初始应力及工况核定。',status:'临时启用；不自动判断结构安全。持续偏移可能被滚动基线吸收，须结合工况和长期趋势复核。'};
const entries=[rules,...payload.knowledge||[]];
function render(){const q=$('kb-search').value.trim().toLowerCase();$('kb-cards').replaceChildren(...entries.filter(e=>Object.values(e).join(' ').toLowerCase().includes(q)).map(e=>{const c=document.createElement('article');c.className='kb-card';for(const [tag,text] of [['small',e.category],['h3',e.title],['b',e.code],['p',e.location],['p',e.summary],['small',e.status]]){const n=document.createElement(tag);n.textContent=text;c.append(n)}if(e.available===false){const note=document.createElement('small');note.textContent=e.availability_note;c.append(note)}else{const a=document.createElement('a');a.href=e.url;a.target='_blank';a.rel='noopener';a.textContent=e.category==='本地规范'?'打开本地PDF原文 ↗':e.category==='项目规则'?'查看完整规则 ↗':'查看原始来源 ↗';c.append(a)}return c}));if(!$('kb-cards').children.length)$('kb-cards').textContent='未找到匹配资料';}
$('kb-search').oninput=render;
const old=showPage;showPage=function(key){old(key);root.hidden=key!=='knowledge'};
window.addEventListener('hashchange',()=>showPage(location.hash.slice(1)));
$('mw-rules').onclick=()=>{location.hash='knowledge';$('kb-search').value='项目暂定';render()};
document.querySelector('.knowledge [data-slot="知识库"]').onclick=()=>{ $('kb-search').value='';render();root.scrollTop=0;location.hash='knowledge';showPage('knowledge') };
render();showPage(location.hash.slice(1)||'home');
})();
