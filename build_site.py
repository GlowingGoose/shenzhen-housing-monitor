"""Validate and publish only public housing statistics and static site files."""
from pathlib import Path
from datetime import datetime, timezone
import json
import shutil
import pandas as pd
from housing_monitor import build_signal

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
    history = []
    for month, group in data.groupby('月份', sort=True):
        sz = group[group['城市']=='深圳'].set_index('市场')
        used = group[group['市场']=='二手']
        history.append({'month':month, 'newMom':float(sz.loc['新房','环比变动_pct']),
            'newYoy':float(sz.loc['新房','同比变动_pct']), 'usedMom':float(sz.loc['二手','环比变动_pct']),
            'usedYoy':float(sz.loc['二手','同比变动_pct']), 'up':int((used['环比变动_pct']>0).sum()),
            'flat':int((used['环比变动_pct']==0).sum()), 'down':int((used['环比变动_pct']<0).sum()),
            'source':sz.loc['二手','来源']})
    status_file = ROOT / 'data/status.json'
    status = json.loads(status_file.read_text()) if status_file.exists() else {'ok':None,'checkedAt':None,'message':'待首次在线检查'}
    payload = {'latest':latest, 'generatedAt':datetime.now(timezone.utc).isoformat(),
        'status':status, 'signal':build_signal(data), 'history':history,
        'records':data[['月份','城市','城市等级','市场','环比变动_pct','同比变动_pct','来源']].values.tolist(),
        'cities':data[data['月份']==latest][['城市','城市等级','市场','环比变动_pct','同比变动_pct','来源']].to_dict('records')}
    dest = ROOT / 'dist'
    shutil.copytree(ROOT/'site', dest, dirs_exist_ok=True)
    (dest/'dashboard.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    # No salary, assets, precise work address, or personal budget in published files.
    public_cols = ['月份','城市','城市等级','市场','环比指数','环比变动_pct','同比指数','同比变动_pct','来源']
    data[public_cols].to_csv(dest/'70city.csv',index=False,encoding='utf-8-sig')
    (dest/'.nojekyll').touch()
    print(f'Built {len(history)} months, latest {latest}, {len(data)} records')

if __name__ == '__main__':
    build()
