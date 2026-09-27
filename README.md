# 深圳住宅观察

国家统计局70城住宅价格监控和静态看板，部署于 GitHub Pages。

## 内容

- 深圳新房、二手房环比与同比趋势，近3/6个月累计变动。
- 全国70城涨跌广度、排序、城市搜索、历史数据及官方来源。
- 数据缺月时断开趋势线，不把非连续月份合并计算。
- 抓取失败保留上次数据、显示异常；浏览器根据当前时间提示数据陈旧。
- 仓库和网页仅包含公开房价数据，不包含个人资产、薪资或住址。

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

初始库为14个已核验月份：2024—2025年保留原文件抽样月份，2026年1—8月连续；不是完整的2023—2026历史库。原始城市等级汇总存在冲突，未纳入公开看板。来源链接存于每条记录中。

深圳二手连续3个月上涨且同比仍负，描述为“结构性回暖”；同比非负时描述为“上行阶段”；其余“走势待确认”。规则用于描述已发生行情，未经预测回测，不提供买卖指令。此前“便宜5%”或“上涨城市达到35个”的阈值未获验证，因此未作为自动买卖条件。

国家统计局城市指数不代表宝安某个小区。具体交易还需结合真实成交、库存、通勤、税费及个人可负担性；无法通过该指数确定底部或顶部。

官方网站：https://www.stats.gov.cn/sj/zxfb/
