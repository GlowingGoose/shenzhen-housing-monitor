# 深圳住宅观察

国家统计局70城住宅价格监控和静态看板，部署于 GitHub Pages。

## 内容

- 一张全景热力图覆盖70城全部历史月份，默认同时显示新房和二手房。
- 支持城市多选、城市等级快捷选择、住宅类型、环比/同比及月份范围筛选。
- 可切换折线图比较所选城市；点击数据查看环比、同比和官方原文。
- 公开CSV下载；抓取失败保留上一份数据并显示状态。

## 自动更新

GitHub Actions 每天北京时间10:23检查国家统计局最近发布列表，支持手动运行。月报发布后自动更新并重新部署。GitHub计划任务可能延迟；页面显示检查时间与状态。每次检查会提交状态，留下可审计记录。若工作流被禁用，应在 Actions 页重新启用。

首次部署：仓库 Settings → Pages → Source 选择 GitHub Actions，再运行 `Update housing dashboard`。无需外部服务器或API密钥；工作流使用仓库自带的短期 GITHUB_TOKEN。

## 本地运行

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python refresh.py
.venv/bin/python build_site.py
.venv/bin/python -m http.server 8080 --directory dist
```

## 数据与规则

历史库已逐月补齐2023年1月至2026年8月，共44期、6160条城市记录；每期包含新房和二手房各70城，直接使用国家统计局发布值，不做插值。每条记录保留官方原文链接，月份来源索引见 `data/historical_sources.json`。原始城市等级汇总存在冲突，未纳入公开看板。来源链接存于每条记录中。

深圳二手连续3个月上涨且同比仍负，描述为“结构性回暖”；同比非负时描述为“上行阶段”；其余“走势待确认”。规则用于描述已发生行情，未经预测回测，不提供买卖指令。此前“便宜5%”或“上涨城市达到35个”的阈值未获验证，因此未作为自动买卖条件。

国家统计局城市指数不代表宝安某个小区。具体交易还需结合真实成交、库存、通勤、税费及个人可负担性；无法通过该指数确定底部或顶部。

官方网站：https://www.stats.gov.cn/sj/zxfb/
