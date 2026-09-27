"""Refresh atomically; on failure retain data and expose failure on the dashboard."""
from pathlib import Path
from datetime import datetime, timezone
import json
import sys
import pandas as pd
from housing_monitor import discover_latest_release, parse_release, build_signal

ROOT = Path(__file__).resolve().parent

def refresh():
    folder = ROOT/'data'
    folder.mkdir(exist_ok=True)
    status_path = folder/'status.json'
    prior = json.loads(status_path.read_text()) if status_path.exists() else {}
    now = datetime.now(timezone.utc).isoformat()
    try:
        month, url = discover_latest_release()
        fresh = parse_release(month, url)
        path = folder/'official_70city_prices.csv'
        old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=fresh.columns)
        if not old.empty and month < old['月份'].max():
            raise ValueError('官方列表早于现存数据，需要人工核对')
        if not old.empty and set(fresh['城市']) != set(old['城市']):
            raise ValueError('70城名单变化，需要人工核对')
        combined = pd.concat([old,fresh],ignore_index=True).drop_duplicates(['月份','城市','市场'],keep='last')
        combined = combined.sort_values(['月份','市场','城市'])
        signal = build_signal(combined)
        temp = path.with_suffix('.tmp')
        combined.to_csv(temp,index=False,encoding='utf-8-sig')
        temp.replace(path)
        (folder/'shenzhen_signal.json').write_text(json.dumps(signal,ensure_ascii=False,indent=2),encoding='utf-8')
        status={'ok':True,'checkedAt':now,'lastSuccess':now,'month':month,'message':'已核验国家统计局最新发布页','source':url}
    except Exception as error:
        status={'ok':False,'checkedAt':now,'lastSuccess':prior.get('lastSuccess'),'message':str(error)[:350]}
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False))
    return 0 if status['ok'] else 1

if __name__ == '__main__':
    sys.exit(refresh())
