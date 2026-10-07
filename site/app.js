const $=id=>document.getElementById(id), safe=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),pct=v=>v==null?'缺失':`${v>0?'+':''}${v.toFixed(1)}%`;
const serial=s=>{const [y,m]=s.split('-').map(Number);return y*12+m-1;};
let model,months,cities,selected=new Set(),lookup=new Map(),activeRows=[],activeMonths=[];
function source(u){try{const x=new URL(u);return x.protocol==='https:'&&(x.hostname.endsWith('.stats.gov.cn')||x.hostname==='www.cih-index.com')?safe(u):'#';}catch{return '#';}}
function cityList(){const q=$('search').value.trim();$('cityList').innerHTML=cities.filter(c=>c.name.includes(q)).map(c=>`<label class="city-option"><input type="checkbox" value="${safe(c.name)}" ${selected.has(c.name)?'checked':''}>${safe(c.name)}<small>${c.tier}</small></label>`).join('');$('count').textContent=`${selected.size} / ${cities.length}`;}
function renderYields(){
 const rows=model.yields.filter(r=>r[0]===model.yieldLatest&&selected.has(r[1])).sort((a,b)=>b[4]-a[4]);
 const max=Math.max(1,...rows.map(r=>r[4]));
 $('yieldRows').innerHTML=rows.length?rows.map(r=>`<tr class="${r[1]==='深圳'?'focus-city':''}"><td>${safe(r[1])}</td><td><span class="bar" style="width:${Math.round(r[4]/max*85)}px"></span>${r[4].toFixed(2)}%</td><td>${r[3].toFixed(2)}</td><td>${Math.round(r[2]).toLocaleString('zh-CN')}</td><td>${r[5].toFixed(1)}年</td><td><span class="source-links"><a href="${source(r[6])}" target="_blank" rel="noopener">房价 ↗</a><a href="${source(r[7])}" target="_blank" rel="noopener">租金 ↗</a></span></td></tr>`).join(''):'<tr><td colspan="6">请选择城市。</td></tr>';
 $('yieldSummary').textContent=`${rows.length} 座已选城市；覆盖 ${model.yields.filter(r=>r[0]===model.yieldLatest).length} 座可比城市。`;
}
function getRow(city,market,month){return lookup.get([city,market,month].join('|'));}
function showDetail(city,market,month){const r=getRow(city,market,month);$('details').innerHTML=r?`<b>${safe(city)} · ${market==='二手'?'二手房':'新房'} · ${month}</b>　环比 ${pct(r[4])}　同比 ${pct(r[5])}<a target="_blank" rel="noopener" href="${source(r[6])}">国家统计局原文 ↗</a>`:'该月缺少官方数据。';}
function color(v,max){if(v==null)return '#dce1e5';const t=Math.min(1,Math.abs(v)/max),a=[248,248,246],b=v>=0?[178,24,43]:[33,102,172];return `rgb(${a.map((x,i)=>Math.round(x+(b[i]-x)*t)).join(',')})`;}
function render(){
 cityList();renderYields();const start=$('start').value,end=$('end').value,idx=$('metric').value==='mom'?4:5,metric=idx===4?'环比':'同比';
 $('rangeError').textContent=start>end?'起始月份不能晚于结束月份。':'';
 activeMonths=months.filter(m=>m>=start&&m<=end);const markets=$('market').value==='all'?['新房','二手']:[$('market').value];
 activeRows=cities.filter(c=>selected.has(c.name)).flatMap(c=>markets.map(m=>({city:c.name,market:m,label:c.name+' · '+(m==='二手'?'二手房':'新房')})));
 $('chartTitle').textContent=`${metric}变化 · ${$('view').value==='heat'?'全景热力图':'城市趋势'}`;
 $('summary').textContent=`${selected.size} 座城市 · ${markets.length} 类住宅 · ${activeMonths.length} 个月 · ${start} — ${end}`;
 $('details').textContent='点击图中数据，查看环比、同比和官方来源。';
 if(!activeRows.length||!activeMonths.length){$('chart').innerHTML='<div class="empty">请选择城市和有效月份范围。</div>';$('legend').innerHTML='';return;}
 const values=activeRows.flatMap(r=>activeMonths.map(m=>getRow(r.city,r.market,m)?.[idx])).filter(v=>v!=null),max=Math.max(.1,...values.map(Math.abs));
 if($('view').value==='heat'){
  $('legend').innerHTML=`<span>${pct(-max)}</span><span class="gradient"></span><span>${pct(max)}</span>`;
  $('chart').innerHTML=`<table class="heat" aria-label="可比城市月度${metric}热力图" style="min-width:${100+activeMonths.length*25}px"><thead><tr><th>城市 / 住宅</th>${activeMonths.map(m=>`<th><span>${m}</span></th>`).join('')}</tr></thead><tbody>${activeRows.map((r,i)=>`<tr><th>${r.label}</th>${activeMonths.map((m,j)=>{const v=getRow(r.city,r.market,m)?.[idx],label=`${r.label} ${m} ${metric} ${pct(v)}`;return `<td style="background:${color(v,max)}"><button data-row="${i}" data-month="${j}" title="${label}" aria-label="${label}"></button></td>`;}).join('')}</tr>`).join('')}</tbody></table>`;
 }else drawLines(idx);
}
function drawLines(idx){
 const W=1200,H=540,L=65,R=30,T=25,B=45,values=activeRows.flatMap(r=>activeMonths.map(m=>getRow(r.city,r.market,m)?.[idx])).filter(v=>v!=null);
 const min=Math.min(0,...values),max=Math.max(0,...values),pad=Math.max(.2,(max-min)*.08),lo=min-pad,hi=max+pad;
 const x=m=>L+(serial(m)-serial(activeMonths[0]))/Math.max(1,serial(activeMonths.at(-1))-serial(activeMonths[0]))*(W-L-R),y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
 const colors=['#176b91','#bd473f','#7b58a0','#23876b','#ba8124','#bf5a8c','#547e36','#5d65bc'];const col=r=>colors[cities.findIndex(c=>c.name===r.city)%colors.length];
 let out=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="所选城市月度价格趋势">`;
 for(let i=0;i<=5;i++){const v=lo+(hi-lo)*i/5;out+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e1e8ed"/><text x="${L-10}" y="${y(v)+4}" text-anchor="end" fill="#728795" font-size="12">${pct(v)}</text>`;}
 out+=`<line x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}" stroke="#8498a4" stroke-dasharray="4 4"/>`;
 const step=Math.max(1,Math.ceil((activeMonths.length-1)/8));activeMonths.forEach((m,i)=>{if(i===activeMonths.length-1||(i%step===0&&activeMonths.length-1-i>=step))out+=`<text x="${x(m)}" y="${H-12}" text-anchor="middle" font-size="11" fill="#728795">${m}</text>`;});
 activeRows.forEach((r,i)=>{let path='',prev=null;activeMonths.forEach(m=>{const v=getRow(r.city,r.market,m)?.[idx];if(v==null){prev=null;return;}path+=`${prev!==null&&serial(m)===prev+1?'L':'M'}${x(m)},${y(v)} `;prev=serial(m);});out+=`<path class="series" d="${path}" fill="none" stroke="${col(r)}" stroke-width="${activeRows.length>12?1:2}" opacity="${activeRows.length>12?.4:.9}" ${r.market==='二手'?'stroke-dasharray="6 3"':''}><title>${r.label}</title></path>`;
 activeMonths.forEach((m,j)=>{const v=getRow(r.city,r.market,m)?.[idx];if(v!=null)out+=`<circle data-row="${i}" data-month="${j}" cx="${x(m)}" cy="${y(v)}" r="${activeRows.length>12?2:4}" fill="${col(r)}" tabindex="0" role="button" aria-label="${r.label} ${m} ${pct(v)}"><title>${r.label} ${m} ${pct(v)}</title></circle>`;});});
 $('chart').innerHTML=out+'</svg>';$('legend').innerHTML=activeRows.length<=12?activeRows.map(r=>`<span class="key"><i style="background:${col(r)}"></i>${r.label}${r.market==='二手'?'（虚线）':''}</span>`).join(''):'新房实线 / 二手房虚线；多城市总览建议使用热力图。';
}
fetch('dashboard.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error(r.status);return r.json();}).then(d=>{
 model=d;if(!d.records?.length||!d.yields?.length)throw Error('缺少价格或租售比数据');months=[...new Set(d.records.map(r=>r[0]))].sort();cities=[...new Map(d.records.map(r=>[r[1],{name:r[1],tier:r[2]}])).values()].sort((a,b)=>['一线','二线','三线'].indexOf(a.tier)-['一线','二线','三线'].indexOf(b.tier)||a.name.localeCompare(b.name,'zh-CN'));
 selected=new Set(cities.map(c=>c.name));d.records.forEach(r=>lookup.set([r[1],r[3],r[0]].join('|'),r));for(const id of ['start','end'])$(id).innerHTML=months.map(m=>`<option>${m}</option>`).join('');$('end').value=months.at(-1);$('latest').textContent=d.latest;$('yieldLatest').textContent=d.yieldLatest;$('yieldMonth').textContent=d.yieldLatest;
 const sz=d.yields.find(r=>r[0]===d.yieldLatest&&r[1]==='深圳');$('shenzhenYield').textContent=sz?sz[4].toFixed(2)+'%':'—';
 const now=new Date(),stale=now.getFullYear()*12+now.getMonth()-serial(d.latest)>2;
 const warnings=[];
 if(d.status.ok===false)warnings.push('官方价格源检查失败：'+d.status.message);
 if(d.yieldStatus.ok===false)warnings.push('租售比源检查失败，展示上次数据：'+d.yieldStatus.message);
 if(stale)warnings.push('官方价格月份已落后，请检查自动更新');
 $('status').textContent=warnings.length?warnings.join('；'):'两类数据均已核验 · 每天自动检查新月报';
 $('coverage').textContent=`交集 ${cities.length} 城；官方价格 ${months[0]}—${months.at(-1)}，租售比自 ${d.yields[0][0]} 起。两种来源月份分别显示。`;
 $('checked').textContent=`最近检查：官方 ${d.status.checkedAt?new Date(d.status.checkedAt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'—'}；租售比 ${d.yieldStatus.checkedAt?new Date(d.yieldStatus.checkedAt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'—'}`;render();
}).catch(e=>{$('status').textContent='加载失败，请刷新重试：'+e.message;});
['market','metric','start','end','view'].forEach(id=>$(id).addEventListener('change',()=>model&&render()));
$('search').addEventListener('input',()=>model&&cityList());$('cityList').addEventListener('change',e=>{if(e.target.matches('input')){e.target.checked?selected.add(e.target.value):selected.delete(e.target.value);render();}});
document.querySelector('.presets').addEventListener('click',e=>{const p=e.target.dataset.preset;if(!p||!model)return;selected=new Set(cities.filter(c=>p==='all'||c.tier===p||c.name===p).map(c=>c.name));render();});
function inspect(e){const t=e.target.closest('[data-row]');if(t){const r=activeRows[+t.dataset.row];showDetail(r.city,r.market,activeMonths[+t.dataset.month]);}}
$('chart').addEventListener('click',inspect);$('chart').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect(e);}});
