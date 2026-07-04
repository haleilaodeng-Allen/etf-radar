# ETF Radar

个人 ETF 情报雷达：筛选值得关注的 ETF、展示影响链，并把领先指标转成可追溯的预警。

当前第一版以 **159822 新经济ETF** 为样板。页面暂用演示状态数据，目的是先确认你要看的“影响地图”和表达方式；后续再接真实数据源并启用自动更新。

## 文件说明

- `index.html`：网页入口
- `style.css`：页面样式
- `app.js`：读取 JSON 并渲染页面
- `data/etf_profiles.json`：每只 ETF 的低频关系卡
- `data/etf_status.json`：每日状态数据
- `scripts/update_market.py`：后续自动更新脚本模板
- `.github/workflows/daily-update.yml`：后续每日运行工作流

> 这不是自动交易工具。预警用于帮助识别环境变化和训练判断，不构成投资建议。