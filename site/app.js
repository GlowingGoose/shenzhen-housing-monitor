const $ = id => document.getElementById(id);
const pct = x => x == null ? '—' : `${x > 0 ? '+' : ''}${x.toFixed(1)}%`;
const cls = x => x > 0 ? 'positive' : x < 0 ? 'negative' : '';
const safe = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const link = u => { try {const x = new URL(u);return x.protocol==='https:'&&x.hostname.endsWith('.stats.gov.cn')?safe(u):'#';}catch{return '#';}};
const serial = s => {const [y,m] = s.split('-').map(Number);return y*12+m-1;};
let model;
function renderChart(){
  const suffix=$('metric').value, latest=serial(model.latest), history=model.history.filter(r=>$('period').value==='all'||serial(r.month)>=latest-11);
  const W=1080,H=285,L=54,R=20,T=24,B=35;
  const values=history.flatMap(r=>[r['new'+suffix],r['used'+suffix],0]);
  const lo=Math.floor((Math.min(...values)-.15)*10)/10,hi=Math.ceil((Math.max(...values)+.15)*10)/10;
  const first=serial(history[0].month),last=serial(history.at(-1).month);
  const x=m=>L+(serial(m)-first)/Math.max(1,last-first)*(W-L-R),y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
  let svg=`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="深圳${suffix==='Mom'?'环比':'同比'}走势图">`;
  for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4;svg+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e5ecee"/><text x="${L-10}" y="${y(v)+4}" text-anchor="end" font-size="11" fill="#73868d">${v.toFixed(1)}%</text>`;}
  svg+=`<line x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}" stroke="#a5b6bb" stroke-dasharray="4 4"/>`;
  for(const [prefix,color] of [['new','#157e82'],['used','#da7b48']]){
    let path='',prev=null;
    for(const r of history){path+=`${prev!==null&&serial(r.month)===prev+1?'L':'M'}${x(r.month)},${y(r[prefix+suffix])} `;prev=serial(r.month);}
    svg+=`<path d="${path}" fill="none" stroke="${color}" stroke-width="2.5"/>`;
    for(const r of history)svg+=`<circle cx="${x(r.month)}" cy="${y(r[prefix+suffix])}" r="3.5" fill="${color}"><title>${r.month} ${prefix==='new'?'新房':'二手房'} ${pct(r[prefix+suffix])}</title></circle>`;
  }
  history.forEach((r,i)=>{if(history.length<=12||i%2===0||i===history.length-1)svg+=`<text x="${x(r.month)}" y="${H-8}" text-anchor="middle" font-size="10" fill="#73868d">${r.month}</text>`;});
  $('chart').innerHTML=svg+'</svg>';
}
function renderCities(){
  const field=$('sort').value==='mom'?'环比变动_pct':'同比变动_pct',query=$('search').value.trim();
  const rows=model.cities.filter(r=>r.市场===$('market').value).sort((a,b)=>b[field]-a[field]||a.城市.localeCompare(b.城市,'zh-CN'));
  const html=rows.map((r,i)=>({r,rank:rows.findIndex(v=>v[field]===r[field])+1})).filter(({r})=>r.城市.includes(query)).map(({r,rank})=>`<tr class="${r.城市==='深圳'?'highlight':''}"><td>${rank}</td><td>${safe(r.城市)}</td><td>${safe(r.城市等级)}</td><td class="${cls(r.环比变动_pct)}">${pct(r.环比变动_pct)}</td><td class="${cls(r.同比变动_pct)}">${pct(r.同比变动_pct)}</td><td><a href="${link(r.来源)}" target="_blank" rel="noopener">国家统计局 ↗</a></td></tr>`).join('');
  $('cities').innerHTML=html||'<tr><td colspan="6">未找到该城市</td></tr>';
}
function render(){
  const s=model.signal,last=model.history.at(-1),status=model.status;
  $('month').textContent=model.latest;
  $('checked').textContent=status.checkedAt?'检查于 '+new Date(status.checkedAt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'尚未完成在线检查';
  const monthNow=new Date(), nowSerial=monthNow.getFullYear()*12+monthNow.getMonth();
  const stale=nowSerial-serial(model.latest)>2;
  $('status').className='notice'+(status.ok===false?' error':stale||status.ok!==true?' warn':'');
  $('status').textContent=status.ok===false?'最近检查失败，当前展示保留的数据：'+status.message:stale?'数据月份已落后超过两个月，请查看 GitHub Actions 运行状态。':status.ok===true?'数据已核验 · 每天自动检查，有新月报即更新。':'历史数据快照 · 等待首次自动检查。';
  $('metrics').innerHTML=[['二手房 · 环比',last.usedMom,`连续上涨 ${s['深圳二手连续上涨月数']} 个月`],['二手房 · 同比',last.usedYoy,'与去年同月相比'],['新房 · 环比',last.newMom,`同比 ${pct(last.newYoy)}`],['二手房 · 近6月累计',s['深圳二手近6期累计_pct'],'连续月份环比连乘，缺月留空']].map(([label,v,sub])=>`<article class="card"><div class="label">${label}</div><div class="value ${cls(v)}">${pct(v)}</div><small>${safe(sub)}</small></article>`).join('');
  $('stage').textContent=s['深圳阶段'];$('buy').textContent='买入观察：'+s['买入提示'];$('sell').textContent='卖出观察：'+s['卖出提示'];
  const three=s['深圳二手近3期累计_pct'];$('momentum').textContent=`最近3个月二手房累计 ${pct(three)}。上涨幅度收窄时，仍需观察能否延续。`;
  $('breadth').innerHTML=`<span class="up" style="width:${last.up/70*100}%"></span><span class="flat" style="width:${last.flat/70*100}%"></span><span class="down" style="width:${last.down/70*100}%"></span>`;
  $('breadthLabels').innerHTML=`<span class="positive"><b>${last.up}</b> 城上涨</span><span class="muted"><b>${last.flat}</b> 城持平</span><span class="negative"><b>${last.down}</b> 城下跌</span>`;
  $('history').innerHTML=[...model.history].reverse().map(r=>`<tr><td>${r.month}</td>${['newMom','newYoy','usedMom','usedYoy'].map(k=>`<td class="${cls(r[k])}">${pct(r[k])}</td>`).join('')}<td>${r.up} / 70</td><td><a href="${link(r.source)}" target="_blank" rel="noopener">原文 ↗</a></td></tr>`).join('');
  renderChart();renderCities();
}
fetch('dashboard.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).then(data=>{model=data;render();}).catch(e=>{$('status').className='notice error';$('status').textContent='看板数据加载失败，请刷新重试：'+e.message;});
['metric','period'].forEach(id=>$(id).addEventListener('change',()=>model&&renderChart()));
['market','sort'].forEach(id=>$(id).addEventListener('change',()=>model&&renderCities()));
$('search').addEventListener('input',()=>model&&renderCities());
