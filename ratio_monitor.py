"""Collect monthly asking rents and resale prices for a city rent-to-price ratio."""
from __future__ import annotations

import gzip
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from lxml import html as html_parser

from housing_monitor import ALL_CITIES

ROOT = Path(__file__).resolve().parent
RENT_URL = 'https://www.cih-index.com/data/index/rentIndex.html'
SALE_URL = 'https://www.cih-index.com/data/index/esfHouse.html'
MONTH_RE = re.compile(r'^(\d{4})年(\d{1,2})月$')
COLS = ['月份', '城市', '二手挂牌均价_元每平米', '挂牌月租_元每平米',
        '租售比', '租售比_售价相当月租月数', '房价来源', '租金来源']


def fetch_html(url: str) -> str:
    if url not in (RENT_URL, SALE_URL):
        raise ValueError('未批准的数据来源')
    error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; HousingMonitor/1.0)',
                'Accept-Encoding': 'gzip',
            })
            with urlopen(request, timeout=35) as response:
                body = response.read()
                if response.headers.get('Content-Encoding', '').lower() == 'gzip':
                    body = gzip.decompress(body)
                return body.decode('utf-8')
        except (OSError, UnicodeError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f'获取中指页面失败：{url}') from error


def parse_city_prices(html: str, kind: str) -> tuple[str, dict[str, dict]]:
    """Read the JSON state rendered by the publisher; never execute page scripts."""
    if kind not in ('rent', 'sale'):
        raise ValueError(kind)
    tree = html_parser.fromstring(html)
    scripts = tree.xpath('//script[contains(text(), "window.__INITIAL_STATE__")]/text()')
    if len(scripts) != 1:
        raise ValueError('发布页缺少唯一的城市数据状态')
    marker = 'window.__INITIAL_STATE__'
    raw = scripts[0].split(marker, 1)[1].lstrip()
    if not raw.startswith('='):
        raise ValueError('发布页状态格式变化')
    state, _ = json.JSONDecoder().raw_decode(raw[1:].lstrip())
    rows = state.get('data', {}).get('cityIndexInfo')
    expected = 50 if kind == 'rent' else 100
    if not isinstance(rows, list) or len(rows) != expected:
        raise ValueError(f'{kind} 城市数不是 {expected}')
    unit = '元/平方米/月' if kind == 'rent' else '元/平方米'
    cities: dict[str, dict] = {}
    months = set()
    ids = set()
    for row in rows:
        city = row.get('city')
        match = MONTH_RE.fullmatch(str(row.get('date', '')))
        value = row.get('average')
        if not isinstance(city, str) or not city or city in cities or not match:
            raise ValueError('城市或月份缺失、重复')
        if row.get('averageUnit') != unit or not isinstance(value, (int, float)):
            raise ValueError(f'{city} 价格或单位不合法')
        if not math.isfinite(value) or not (0 < value < (1000 if kind == 'rent' else 1_000_000)):
            raise ValueError(f'{city} 价格越界')
        city_id = row.get('cityId')
        if not city_id or city_id in ids:
            raise ValueError('城市 ID 缺失、重复')
        ids.add(city_id)
        month = f'{match.group(1)}-{int(match.group(2)):02d}'
        months.add(month)
        cities[city] = {'value': float(value), 'id': city_id}
    if len(months) != 1:
        raise ValueError('同一页混合了不同月份')
    return months.pop(), cities


def combine(rent_month: str, rents: dict, sale_month: str, sales: dict) -> pd.DataFrame:
    if rent_month != sale_month:
        raise ValueError(f'租金 {rent_month} 与房价 {sale_month} 不在同月')
    common = sorted(ALL_CITIES & rents.keys() & sales.keys())
    if len(common) < 40 or '深圳' not in common:
        raise ValueError(f'三套城市名单的交集异常：{len(common)} 城')
    records = []
    for city in common:
        rent, sale = rents[city], sales[city]
        if rent['id'] != sale['id']:
            raise ValueError(f'{city} 的房价和租金城市 ID 不一致')
        months = sale['value'] / rent['value']
        if not (40 < months < 12000):
            raise ValueError(f'{city} 租售比异常')
        records.append([rent_month, city, sale['value'], rent['value'],
                        f'1:{math.floor(months + 0.5)}', round(months, 2), SALE_URL, RENT_URL])
    return pd.DataFrame(records, columns=COLS)


def refresh() -> int:
    folder = ROOT / 'data'
    folder.mkdir(exist_ok=True)
    status_path = folder / 'ratio_status.json'
    prior = json.loads(status_path.read_text()) if status_path.exists() else {}
    now = datetime.now(timezone.utc).isoformat()
    try:
        rent_month, rents = parse_city_prices(fetch_html(RENT_URL), 'rent')
        sale_month, sales = parse_city_prices(fetch_html(SALE_URL), 'sale')
        fresh = combine(rent_month, rents, sale_month, sales)
        current = datetime.now(timezone.utc)
        source_age = (current.year - int(rent_month[:4])) * 12 + current.month - int(rent_month[5:])
        if source_age > 1 and current.day >= 15:
            raise ValueError(f'中指数据仍停留在 {rent_month}，已超过正常更新窗口')
        path = folder / 'rent_sale_ratio.csv'
        old = pd.read_csv(path, dtype={'月份': str}) if path.exists() else pd.DataFrame(columns=COLS)
        if not old.empty and fresh['月份'].iloc[0] < old['月份'].max():
            raise ValueError('来源月份早于已保存月份')
        if not old.empty:
            prior_cities = set(old[old['月份'] == old['月份'].max()]['城市'])
            if prior_cities != set(fresh['城市']):
                raise ValueError('可比城市名单变化，需要人工核对范围和口径')
        combined = pd.concat([old, fresh], ignore_index=True) if not old.empty else fresh.copy()
        combined = combined.drop_duplicates(['月份', '城市'], keep='last')
        combined = combined.sort_values(['月份', '城市'])
        temp = path.with_suffix('.tmp')
        combined.to_csv(temp, index=False, encoding='utf-8-sig')
        temp.replace(path)
        status = {'ok': True, 'checkedAt': now, 'lastSuccess': now,
                  'month': rent_month, 'cities': len(fresh), 'message': '同月租金与二手房价已核验',
                  'sources': [SALE_URL, RENT_URL]}
    except Exception as exc:
        status = {'ok': False, 'checkedAt': now, 'lastSuccess': prior.get('lastSuccess'),
                  'month': prior.get('month'), 'message': str(exc)[:350]}
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(status, ensure_ascii=False))
    return 0 if status['ok'] else 1


if __name__ == '__main__':
    sys.exit(refresh())
