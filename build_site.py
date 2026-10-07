"""Validate and publish only public housing statistics and static site files."""
from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import pandas as pd
from yield_monitor import COLS

ROOT = Path(__file__).resolve().parent

def build():
    data = pd.read_csv(ROOT / 'data/official_70city_prices.csv')
    if data.duplicated(['月份', '城市', '市场']).any():
        raise ValueError('城市记录重复')
    if not data.groupby(['月份', '市场'])['城市'].nunique().eq(70).all():
        raise ValueError('必须每期每个市场70城')
    if not data[['环比指数','同比指数']].apply(pd.to_numeric, errors='coerce').notna().all().all():
        raise ValueError('指数包含缺失或非数值')
    latest = data['月份'].max()
    yields = pd.read_csv(ROOT / 'data/rent_sale_yield.csv', dtype={'月份': str})
    if list(yields.columns) != COLS or yields.duplicated(['月份', '城市']).any():
        raise ValueError('租售比文件结构或城市月份重复')
    yield_month = yields['月份'].max()
    current = yields[yields['月份'] == yield_month].sort_values('城市')
    matching = set(data['城市']) & set(current['城市'])
    if len(matching) < 40 or '深圳' not in matching or len(matching) != len(current):
        raise ValueError('租售比与70城名单不匹配')
    if not (yields['毛租金回报率_pct'] > 0).all():
        raise ValueError('租金回报率缺失')
    visible = data[data['城市'].isin(matching)].copy()
    status_file = ROOT / 'data/status.json'
    status = json.loads(status_file.read_text()) if status_file.exists() else {'ok':None,'checkedAt':None,'message':'待首次在线检查'}
    yield_status_file = ROOT / 'data/yield_status.json'
    yield_status = json.loads(yield_status_file.read_text()) if yield_status_file.exists() else {'ok':None,'message':'待首次检查'}
    yield_cols = ['月份','城市','二手挂牌均价_元每平米','挂牌月租_元每平米',
                  '毛租金回报率_pct','房价租金年数','房价来源','租金来源']
    payload = {'latest':latest, 'yieldLatest':yield_month,
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'status':status, 'yieldStatus':yield_status,
        'records':visible[['月份','城市','城市等级','市场','环比变动_pct','同比变动_pct','来源']].values.tolist(),
        'yields':yields[yields['城市'].isin(matching)][yield_cols].values.tolist()}
    dest = ROOT / 'dist'
    shutil.copytree(ROOT/'site', dest, dirs_exist_ok=True)
    (dest/'dashboard.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    # No salary, assets, precise work address, or personal budget in published files.
    public_cols = ['月份','城市','城市等级','市场','环比指数','环比变动_pct','同比指数','同比变动_pct','来源']
    visible[public_cols].to_csv(dest/'matched-city-prices.csv',index=False,encoding='utf-8-sig')
    yields[yield_cols].to_csv(dest/'rent-sale-yields.csv',index=False,encoding='utf-8-sig')
    (dest/'.nojekyll').touch()
    print(f'Built {len(matching)} matched cities, price through {latest}, yield through {yield_month}')

if __name__ == '__main__':
    build()
