const $ = id => document.getElementById(id);
const safe = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const pct = value => value == null ? '缺失' : `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
const serial = month => { const [year, number] = month.split('-').map(Number); return year * 12 + number - 1; };

let model, months, cities, selected = new Set(), lookup = new Map();
let activeRows = [], activeMonths = [], activeTab = 'ratio';

function source(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' &&
      (parsed.hostname.endsWith('.stats.gov.cn') || parsed.hostname === 'www.cih-index.com')
      ? safe(url) : '#';
  } catch { return '#'; }
}

function cityList() {
  const query = $('search').value.trim();
  $('cityList').innerHTML = cities.filter(city => city.name.includes(query)).map(city =>
    `<label class="city-option"><input type="checkbox" value="${safe(city.name)}" ${selected.has(city.name) ? 'checked' : ''}>${safe(city.name)}<small>${safe(city.tier)}</small></label>`
  ).join('');
  $('count').textContent = `${selected.size} / ${cities.length}`;
}

function renderRatios() {
  const month = $('ratioSelect').value || model.ratioLatest;
  const rows = model.ratios.filter(row => row[0] === month && selected.has(row[1]))
    .sort((a, b) => a[5] - b[5]);
  $('ratioMonth').textContent = month;
  const shenzhen = model.ratios.find(row => row[0] === month && row[1] === '深圳');
  $('shenzhenRatio').textContent = shenzhen ? shenzhen[4] : '—';
  $('ratioRows').innerHTML = rows.length ? rows.map(row =>
    `<tr class="${row[1] === '深圳' ? 'focus-city' : ''}"><td>${safe(row[1])}</td><td class="ratio-value">${safe(row[4])}</td><td>${row[3].toFixed(2)}</td><td>${Math.round(row[2]).toLocaleString('zh-CN')}</td><td><span class="source-links"><a href="${source(row[6])}" target="_blank" rel="noopener">房价 ↗</a><a href="${source(row[7])}" target="_blank" rel="noopener">租金 ↗</a></span></td></tr>`
  ).join('') : '<tr><td colspan="5">请选择城市。</td></tr>';
  $('ratioSummary').textContent = `${month} · ${rows.length} 座已选城市 · 按 1:N 中的 N 从小到大排列`;
}

function getRow(city, market, month) { return lookup.get([city, market, month].join('|')); }
function showDetail(city, market, month) {
  const row = getRow(city, market, month);
  $('details').innerHTML = row
    ? `<b>${safe(city)} · ${market === '二手' ? '二手房' : '新房'} · ${month}</b>　环比 ${pct(row[4])}　同比 ${pct(row[5])}<a target="_blank" rel="noopener" href="${source(row[6])}">国家统计局原文 ↗</a>`
    : '该月缺少官方数据。';
}
function color(value, max) {
  if (value == null) return '#dce1dc';
  const weight = Math.min(1, Math.abs(value) / max);
  const neutral = [248, 248, 246], strong = value >= 0 ? [178, 24, 43] : [33, 102, 172];
  return `rgb(${neutral.map((start, index) => Math.round(start + (strong[index] - start) * weight)).join(',')})`;
}

function renderPrices() {
  const start = $('start').value, end = $('end').value;
  const index = activeTab === 'mom' ? 4 : 5;
  const metric = activeTab === 'mom' ? '环比' : '同比';
  $('rangeError').textContent = start > end ? '起始月份不能晚于结束月份。' : '';
  activeMonths = months.filter(month => month >= start && month <= end);
  const markets = $('market').value === 'all' ? ['新房', '二手'] : [$('market').value];
  activeRows = cities.filter(city => selected.has(city.name)).flatMap(city => markets.map(market => ({
    city: city.name, market, label: `${city.name} · ${market === '二手' ? '二手房' : '新房'}`
  })));
  $('chartTitle').textContent = `房价${metric}走势`;
  $('summary').textContent = `${selected.size} 座城市 · ${markets.length} 类住宅 · ${activeMonths.length} 个月 · ${start} — ${end}`;
  $('details').textContent = '点击图中数据，查看数值和官方来源。';
  if (!activeRows.length || !activeMonths.length) {
    $('chart').innerHTML = '<div class="empty">请选择城市和有效月份范围。</div>';
    $('legend').innerHTML = '';
    return;
  }
  const values = activeRows.flatMap(row => activeMonths.map(month => getRow(row.city, row.market, month)?.[index])).filter(value => value != null);
  const max = Math.max(.1, ...values.map(Math.abs));
  if ($('view').value === 'heat') {
    $('legend').innerHTML = `<span>${pct(-max)}</span><span class="gradient"></span><span>${pct(max)}</span>`;
    $('chart').innerHTML = `<table class="heat" aria-label="可比城市月度${metric}热力图" style="min-width:${100 + activeMonths.length * 25}px"><thead><tr><th>城市 / 住宅</th>${activeMonths.map(month => `<th><span>${month}</span></th>`).join('')}</tr></thead><tbody>${activeRows.map((row, rowIndex) => `<tr><th>${safe(row.label)}</th>${activeMonths.map((month, monthIndex) => {
      const value = getRow(row.city, row.market, month)?.[index];
      const label = `${row.label} ${month} ${metric} ${pct(value)}`;
      return `<td style="background:${color(value, max)}"><button data-row="${rowIndex}" data-month="${monthIndex}" title="${safe(label)}" aria-label="${safe(label)}"></button></td>`;
    }).join('')}</tr>`).join('')}</tbody></table>`;
  } else drawLines(index);
}

function drawLines(index) {
  const W = 1200, H = 540, L = 65, R = 30, T = 25, B = 45;
  const values = activeRows.flatMap(row => activeMonths.map(month => getRow(row.city, row.market, month)?.[index])).filter(value => value != null);
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const pad = Math.max(.2, (max - min) * .08), low = min - pad, high = max + pad;
  const x = month => L + (serial(month) - serial(activeMonths[0])) / Math.max(1, serial(activeMonths.at(-1)) - serial(activeMonths[0])) * (W - L - R);
  const y = value => T + (high - value) / (high - low) * (H - T - B);
  const palette = ['#1d4838', '#b35e42', '#755d9f', '#257f78', '#a28237', '#ba5c80', '#547e36', '#4b66a6'];
  const lineColor = row => palette[cities.findIndex(city => city.name === row.city) % palette.length];
  let output = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="所选城市月度价格趋势">`;
  for (let i = 0; i <= 5; i++) {
    const value = low + (high - low) * i / 5;
    output += `<line x1="${L}" x2="${W-R}" y1="${y(value)}" y2="${y(value)}" stroke="#e1e8df"/><text x="${L-10}" y="${y(value)+4}" text-anchor="end" fill="#728795" font-size="12">${pct(value)}</text>`;
  }
  output += `<line x1="${L}" x2="${W-R}" y1="${y(0)}" y2="${y(0)}" stroke="#879987" stroke-dasharray="4 4"/>`;
  const step = Math.max(1, Math.ceil((activeMonths.length - 1) / 8));
  activeMonths.forEach((month, i) => {
    if (i === activeMonths.length - 1 || (i % step === 0 && activeMonths.length - 1 - i >= step))
      output += `<text x="${x(month)}" y="${H-12}" text-anchor="middle" font-size="11" fill="#728795">${month}</text>`;
  });
  activeRows.forEach((row, rowIndex) => {
    let path = '', previous = null;
    activeMonths.forEach(month => {
      const value = getRow(row.city, row.market, month)?.[index];
      if (value == null) { previous = null; return; }
      path += `${previous !== null && serial(month) === previous + 1 ? 'L' : 'M'}${x(month)},${y(value)} `;
      previous = serial(month);
    });
    output += `<path class="series" d="${path}" fill="none" stroke="${lineColor(row)}" stroke-width="${activeRows.length > 12 ? 1 : 2}" opacity="${activeRows.length > 12 ? .4 : .9}" ${row.market === '二手' ? 'stroke-dasharray="6 3"' : ''}><title>${safe(row.label)}</title></path>`;
    activeMonths.forEach((month, monthIndex) => {
      const value = getRow(row.city, row.market, month)?.[index];
      if (value != null) output += `<circle data-row="${rowIndex}" data-month="${monthIndex}" cx="${x(month)}" cy="${y(value)}" r="${activeRows.length > 12 ? 2 : 4}" fill="${lineColor(row)}" tabindex="0" role="button" aria-label="${safe(row.label)} ${month} ${pct(value)}"><title>${safe(row.label)} ${month} ${pct(value)}</title></circle>`;
    });
  });
  $('chart').innerHTML = output + '</svg>';
  $('legend').innerHTML = activeRows.length <= 12
    ? activeRows.map(row => `<span class="key"><i style="background:${lineColor(row)}"></i>${safe(row.label)}${row.market === '二手' ? '（虚线）' : ''}</span>`).join('')
    : '新房实线 / 二手房虚线；多城市总览建议使用热力图。';
}

function render() {
  cityList();
  renderRatios();
  if (activeTab !== 'ratio') renderPrices();
}
function switchTab(tab) {
  activeTab = tab;
  for (const name of ['ratio', 'mom', 'yoy']) {
    const button = $(`tab-${name}`), isActive = name === tab;
    button.classList.toggle('is-active', isActive);
    button.setAttribute('aria-selected', String(isActive));
    button.tabIndex = isActive ? 0 : -1;
  }
  $('panel-ratio').hidden = tab !== 'ratio';
  $('panel-price').hidden = tab === 'ratio';
  $('panel-price').setAttribute('aria-labelledby', `tab-${tab === 'ratio' ? 'mom' : tab}`);
  if (model) render();
}

fetch('dashboard.json', {cache: 'no-store'}).then(response => {
  if (!response.ok) throw Error(response.status);
  return response.json();
}).then(data => {
  model = data;
  if (!data.records?.length || !data.ratios?.length) throw Error('缺少价格或租售比数据');
  months = [...new Set(data.records.map(row => row[0]))].sort();
  cities = [...new Map(data.records.map(row => [row[1], {name: row[1], tier: row[2]}])).values()]
    .sort((a, b) => ['一线', '二线', '三线'].indexOf(a.tier) - ['一线', '二线', '三线'].indexOf(b.tier) || a.name.localeCompare(b.name, 'zh-CN'));
  selected = new Set(cities.map(city => city.name));
  data.records.forEach(row => lookup.set([row[1], row[3], row[0]].join('|'), row));
  for (const id of ['start', 'end']) $(id).innerHTML = months.map(month => `<option>${month}</option>`).join('');
  $('end').value = months.at(-1);
  $('latest').textContent = data.latest;
  $('ratioLatest').textContent = data.ratioLatest;
  const ratioMonths = [...new Set(data.ratios.map(row => row[0]))].sort();
  $('ratioSelect').innerHTML = ratioMonths.map(month => `<option>${month}</option>`).join('');
  $('ratioSelect').value = data.ratioLatest;
  const now = new Date(), stale = now.getFullYear() * 12 + now.getMonth() - serial(data.latest) > 2;
  const warnings = [];
  if (data.status.ok === false) warnings.push('官方价格源检查失败：' + data.status.message);
  if (data.ratioStatus.ok === false) warnings.push('租售比源检查失败，展示上次数据：' + data.ratioStatus.message);
  if (stale) warnings.push('官方价格月份已落后，请检查自动更新');
  $('status').textContent = warnings.length ? warnings.join('；') : '两类数据均已核验 · 每天自动检查新月报';
  $('status').classList.toggle('is-warning', warnings.length > 0);
  $('coverage').textContent = `交集 ${cities.length} 城；官方房价指数 ${months[0]}—${months.at(-1)}，租售比自 ${data.ratios[0][0]} 起。两类数据月份分别显示。`;
  $('checked').textContent = `最近检查：统计局 ${data.status.checkedAt ? new Date(data.status.checkedAt).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) : '—'}；中指 ${data.ratioStatus.checkedAt ? new Date(data.ratioStatus.checkedAt).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) : '—'}`;
  switchTab('ratio');
}).catch(error => { $('status').textContent = '加载失败，请刷新重试：' + error.message; $('status').classList.add('is-warning'); });

for (const id of ['market', 'start', 'end', 'view']) $(id).addEventListener('change', () => model && renderPrices());
$('ratioSelect').addEventListener('change', () => model && renderRatios());
$('search').addEventListener('input', () => model && cityList());
$('cityList').addEventListener('change', event => {
  if (event.target.matches('input')) {
    event.target.checked ? selected.add(event.target.value) : selected.delete(event.target.value);
    render();
  }
});
document.querySelector('.presets').addEventListener('click', event => {
  const preset = event.target.dataset.preset;
  if (!preset || !model) return;
  selected = new Set(cities.filter(city => preset === 'all' || city.tier === preset || city.name === preset).map(city => city.name));
  render();
});
document.querySelector('.tabs').addEventListener('click', event => {
  const tab = event.target.dataset.tab;
  if (tab) switchTab(tab);
});
document.querySelector('.tabs').addEventListener('keydown', event => {
  const options = ['ratio', 'mom', 'yoy'], index = options.indexOf(activeTab);
  const next = event.key === 'ArrowRight' ? (index + 1) % 3 : event.key === 'ArrowLeft' ? (index + 2) % 3 : event.key === 'Home' ? 0 : event.key === 'End' ? 2 : null;
  if (next !== null) { event.preventDefault(); switchTab(options[next]); $(`tab-${options[next]}`).focus(); }
});
function inspect(event) {
  const target = event.target.closest('[data-row]');
  if (target) {
    const row = activeRows[+target.dataset.row];
    showDetail(row.city, row.market, activeMonths[+target.dataset.month]);
  }
}
$('chart').addEventListener('click', inspect);
$('chart').addEventListener('keydown', event => {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); inspect(event); }
});
