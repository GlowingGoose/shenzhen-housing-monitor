"""Validate and publish only public housing statistics and static site files."""
from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import pandas as pd
from ratio_monitor import COLS

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
    ratios = pd.read_csv(ROOT / 'data/rent_sale_ratio.csv', dtype={'月份': str})
    if list(ratios.columns) != COLS or ratios.duplicated(['月份', '城市']).any():
        raise ValueError('租售比文件结构或城市月份重复')
    ratio_month = ratios['月份'].max()
    current = ratios[ratios['月份'] == ratio_month].sort_values('城市')
    matching = set(data['城市']) & set(current['城市'])
    if len(matching) < 40 or '深圳' not in matching or len(matching) != len(current):
        raise ValueError('租售比与70城名单不匹配')
    numeric = ratios[['二手挂牌均价_元每平米', '挂牌月租_元每平米', '租售比_售价相当月租月数']]
    if not numeric.apply(pd.to_numeric, errors='coerce').notna().all().all() or not numeric.gt(0).all().all():
        raise ValueError('租售比输入缺失或异常')
    computed = ratios['二手挂牌均价_元每平米'] / ratios['挂牌月租_元每平米']
    if (computed - ratios['租售比_售价相当月租月数']).abs().gt(0.011).any():
        raise ValueError('租售比与挂牌价格不一致')
    expected_labels = computed.map(lambda value: f'1:{int(value + 0.5)}')
    if not ratios['租售比'].eq(expected_labels).all():
        raise ValueError('租售比文本与挂牌价格不一致')
    visible = data[data['城市'].isin(matching)].copy()
    status_file = ROOT / 'data/status.json'
    status = json.loads(status_file.read_text()) if status_file.exists() else {'ok':None,'checkedAt':None,'message':'待首次在线检查'}
    ratio_status_file = ROOT / 'data/ratio_status.json'
    ratio_status = json.loads(ratio_status_file.read_text()) if ratio_status_file.exists() else {'ok':None,'message':'待首次检查'}
    payload = {'latest':latest, 'ratioLatest':ratio_month,
        'generatedAt':datetime.now(timezone.utc).isoformat(),
        'status':status, 'ratioStatus':ratio_status,
        'records':visible[['月份','城市','城市等级','市场','环比变动_pct','同比变动_pct','来源']].values.tolist(),
        'ratios':ratios[ratios['城市'].isin(matching)][COLS].values.tolist()}
    dest = ROOT / 'dist'
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ROOT/'site', dest)
    (dest/'dashboard.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    # No salary, assets, precise work address, or personal budget in published files.
    public_cols = ['月份','城市','城市等级','市场','环比指数','环比变动_pct','同比指数','同比变动_pct','来源']
    visible[public_cols].to_csv(dest/'matched-city-prices.csv',index=False,encoding='utf-8-sig')
    ratios[COLS].to_csv(dest/'rent-sale-ratios.csv',index=False,encoding='utf-8-sig')
    (dest/'.nojekyll').touch()
    print(f'Built {len(matching)} matched cities, price through {latest}, ratio through {ratio_month}')

if __name__ == '__main__':
    build()
