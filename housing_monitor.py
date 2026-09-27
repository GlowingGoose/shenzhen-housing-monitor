#!/usr/bin/env python3
"""Monitor NBS 70-city residential price releases and emit clean CSV/JSON outputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import math
from datetime import datetime
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

import pandas as pd
from lxml import html as html_parser


INDEX_URL = "https://www.stats.gov.cn/sj/zxfb/"
TITLE_RE = re.compile(r"(\d{4})年(\d{1,2})月份70个大中城市商品住宅销售价格变动情况")
FIRST_TIER = {"北京", "上海", "广州", "深圳"}
SECOND_TIER = {
    "天津", "石家庄", "太原", "呼和浩特", "沈阳", "大连", "长春", "哈尔滨",
    "南京", "杭州", "宁波", "合肥", "福州", "厦门", "南昌", "济南", "青岛",
    "郑州", "武汉", "长沙", "南宁", "海口", "重庆", "成都", "贵阳", "昆明",
    "西安", "兰州", "西宁", "银川", "乌鲁木齐",
}
THIRD_TIER = set('唐山 秦皇岛 包头 丹东 锦州 吉林 牡丹江 无锡 徐州 扬州 温州 金华 蚌埠 安庆 泉州 九江 赣州 烟台 济宁 洛阳 平顶山 宜昌 襄阳 岳阳 常德 韶关 湛江 惠州 桂林 北海 三亚 泸州 南充 遵义 大理'.split())
ALL_CITIES = FIRST_TIER | SECOND_TIER | THIRD_TIER


def clean_city(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", "", text)


def tier(city: str) -> str:
    if city in FIRST_TIER:
        return "一线"
    if city in SECOND_TIER:
        return "二线"
    return "三线"


def get_html(url: str, timeout: int = 45) -> str:
    if urlparse(url).scheme != 'https' or not (urlparse(url).hostname or '').endswith('.stats.gov.cn'):
        raise ValueError('仅接受国家统计局 HTTPS 来源')
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NBSHousingMonitor/1.0)"}
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                return response.read().decode('utf-8')
        except (URLError, OSError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"抓取失败：{url}") from last_error


def discover_latest_release() -> tuple[str, str]:
    candidates: list[tuple[str, str, str]] = []
    for page in range(4):
        index_url = INDEX_URL if page == 0 else urljoin(INDEX_URL, f'index_{page}.html')
        tree = html_parser.fromstring(get_html(index_url))
        for anchor in tree.xpath('//a[@href]'):
            title = clean_city(anchor.text_content())
            match = TITLE_RE.fullmatch(title)
            if match:
                month = f'{match.group(1)}-{int(match.group(2)):02d}'
                candidates.append((month, title, urljoin(index_url, anchor.get('href'))))
        if candidates:
            break
    if not candidates:
        raise RuntimeError("国家统计局数据发布页未找到70城房价信息")
    month, _, url = max(candidates, key=lambda item: item[0])
    return month, url


def _parse_overall_table(table: pd.DataFrame, month: str, market: str, url: str) -> list[dict]:
    records: list[dict] = []
    half = table.shape[1] // 2
    for _, row in table.iterrows():
        for offset in (0, half):
            city = clean_city(row.iloc[offset])
            if city not in ALL_CITIES:
                continue
            try:
                mom_index = float(row.iloc[offset + 1])
                yoy_index = float(row.iloc[offset + 2])
            except (TypeError, ValueError):
                continue
            if not all(math.isfinite(v) and 0 < v < 200 for v in (mom_index, yoy_index)):
                raise ValueError(f'指数不合法：{city}')
            records.append({
                "月份": month,
                "城市": city,
                "城市等级": tier(city),
                "市场": market,
                "环比指数": mom_index,
                "环比变动_pct": round(mom_index - 100, 1),
                "同比指数": yoy_index,
                "同比变动_pct": round(yoy_index - 100, 1),
                "来源": url,
                "抓取时间": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
    return records


def parse_release(month: str, url: str) -> pd.DataFrame:
    html = get_html(url)
    page_title = html_parser.fromstring(html).xpath('//title/text()')
    match = TITLE_RE.search(clean_city(''.join(page_title)))
    if not match or f'{match.group(1)}-{int(match.group(2)):02d}' != month:
        raise ValueError('发布页标题与请求月份不一致')
    tables = pd.read_html(StringIO(html))
    overall = [t for t in tables if t.shape[1] in (6, 8) and len(t) >= 35]
    if len(overall) < 2:
        raise RuntimeError(f"未识别到新房、二手房总表：{url}")
    records = _parse_overall_table(overall[0], month, "新房", url)
    records += _parse_overall_table(overall[1], month, "二手", url)
    data = pd.DataFrame(records)
    if data.duplicated(['月份', '城市', '市场']).any():
        raise ValueError('发布页有重复城市记录')
    counts = data.groupby("市场")["城市"].nunique().to_dict()
    if counts != {"二手": 70, "新房": 70}:
        raise RuntimeError(f"城市数量校验失败：{counts}，来源：{url}")
    if "深圳" not in set(data["城市"]):
        raise RuntimeError("未找到深圳数据")
    if set(data['城市']) != ALL_CITIES:
        raise ValueError('城市名单不完整')
    if set(data[data['市场']=='新房']['城市']) != set(data[data['市场']=='二手']['城市']):
        raise ValueError('新房和二手城市名单不一致')
    return data.sort_values(["月份", "市场", "城市"]).reset_index(drop=True)


def upsert_csv(data: pd.DataFrame, path: Path) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_csv(path, dtype={"月份": str})
        data = pd.concat([old, data], ignore_index=True)
    data = data.drop_duplicates(["月份", "城市", "市场"], keep="last")
    data = data.sort_values(["月份", "市场", "城市"]).reset_index(drop=True)
    data.to_csv(path, index=False, encoding="utf-8-sig")
    return data


def build_signal(data: pd.DataFrame) -> dict:
    shenzhen = data[data["城市"] == "深圳"].copy()
    months = sorted(shenzhen["月份"].unique())
    if not months:
        raise RuntimeError("数据中没有深圳")
    latest = months[-1]
    recent_months = months[-3:]
    latest_rows = shenzhen[shenzhen["月份"] == latest].set_index("市场")
    used_all = shenzhen[shenzhen["市场"] == "二手"].sort_values("月份")
    new_all = shenzhen[shenzhen["市场"] == "新房"].sort_values("月份")
    used = used_all.tail(3)
    new = new_all.tail(3)
    used_cum = (used["环比指数"].div(100).prod() - 1) * 100
    new_cum = (new["环比指数"].div(100).prod() - 1) * 100
    def positive_streak(frame: pd.DataFrame) -> int:
        count = 0
        expected = pd.Period(latest, freq='M')
        for _, row in frame.iloc[::-1].iterrows():
            if row['环比变动_pct'] > 0 and pd.Period(row['月份'], freq='M') == expected:
                count += 1
                expected -= 1
            else:
                break
        return count

    def cumulative(frame: pd.DataFrame, length: int):
        tail = frame.tail(length)
        expected = list(pd.period_range(end=latest, periods=length, freq='M').astype(str))
        if tail['月份'].tolist() != expected:
            return None
        return round((tail['环比指数'].div(100).prod() - 1) * 100, 2)

    used_streak = positive_streak(used_all)
    new_streak = positive_streak(new_all)
    used_cum, new_cum = cumulative(used_all, 3), cumulative(new_all, 3)
    used_6m, new_6m = cumulative(used_all, 6), cumulative(new_all, 6)
    latest_all = data[(data["月份"] == latest) & (data["市场"] == "二手")]
    breadth = int((latest_all["环比变动_pct"] > 0).sum())
    used_yoy = float(latest_rows.loc["二手", "同比变动_pct"])
    if used_streak >= 3 and used_yoy < 0:
        stage = "结构性回暖"
        buy = "出现回暖信号；结合预算与小区成交评估"
        sell = "观察本小区成交速度与议价空间"
    elif used_streak >= 3 and used_yoy >= 0:
        stage = "上行阶段"
        buy = "连续上涨且同比转正；核对成交价与持有成本"
        sell = "可结合小区成交量评估出售"
    else:
        stage = "走势待确认"
        buy = "继续观察并筛选房源"
        sell = "价格信号偏弱"
    return {
        "最新月份": latest,
        "深圳阶段": stage,
        "买入提示": buy,
        "卖出提示": sell,
        "深圳新房环比_pct": float(latest_rows.loc["新房", "环比变动_pct"]),
        "深圳新房同比_pct": float(latest_rows.loc["新房", "同比变动_pct"]),
        "深圳二手环比_pct": float(latest_rows.loc["二手", "环比变动_pct"]),
        "深圳二手同比_pct": used_yoy,
        "深圳新房近3期累计_pct": new_cum,
        "深圳二手近3期累计_pct": used_cum,
        "深圳新房近6期累计_pct": new_6m,
        "深圳二手近6期累计_pct": used_6m,
        "深圳二手连续上涨月数": used_streak,
        "深圳新房连续上涨月数": new_streak,
        "70城二手环比上涨城市数": breadth,
        "纳入判断的最近月份": recent_months,
        "说明": "国家统计局城市指数是宏观信号，具体交易仍需核对目标小区真实成交价、挂牌量和议价率。",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="指定国家统计局发布页；默认自动发现最新一期")
    parser.add_argument("--month", help="指定月份，格式YYYY-MM；与--url同时使用")
    parser.add_argument("--data", default="data/official_70city_prices.csv")
    parser.add_argument("--signal", default="data/shenzhen_signal.json")
    args = parser.parse_args()
    if args.url:
        if not args.month:
            parser.error("使用--url时必须同时提供--month")
        month, url = args.month, args.url
    else:
        month, url = discover_latest_release()
    fresh = parse_release(month, url)
    all_data = upsert_csv(fresh, Path(args.data))
    signal = build_signal(all_data)
    signal["来源"] = url
    signal_path = Path(args.signal)
    signal_path.parent.mkdir(parents=True, exist_ok=True)
    signal_path.write_text(json.dumps(signal, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(signal, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
