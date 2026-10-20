# 全年 Dashboard 与分析输出验收证据

> 执行日期：2026-10-20（Asia/Shanghai）  
> 数据库：本地 MySQL 8.0.44，项目库 `city_air_quality_etl`  
> 输出：Git Ignore 下的 `outputs/latest/`

## Acceptance → Evidence

| Acceptance | 实际证据 | 状态 |
| --- | --- | --- |
| 真实数据库生成 | 使用 MySQL Clean 1,905 条和 Quality Log 469 条生成报告 | VERIFIED |
| 六类输出 | Dashboard、Clean CSV、Quality CSV、City Summary、Monthly Summary、Markdown Report 均生成 | VERIFIED |
| 五城市覆盖 | 北京、上海、广州、成都、武汉各 381 条 | VERIFIED |
| 来源构成 | 历史 CSV 1,825、API 80 | VERIFIED |
| 日期范围 | `2025-01-01`～`2026-10-19` | VERIFIED |
| 月度对账 | 65 行月度汇总，13 个月 × 5 城市，记录数合计 1,905 | VERIFIED |
| 缺失边界 | AQI 有效样本 1,838；67 条 Record 含缺失；未执行填充 | VERIFIED |
| 时间断档 | 历史 CSV 与 API 使用独立 Plotly Trace，不跨来源连线 | VERIFIED |
| 桌面视觉检查 | 七张图表完整渲染，无裁切 | VERIFIED |
| 窄屏视觉检查 | 390px 页面无整体溢出，复杂图表在 Panel 内横向滚动 | VERIFIED |
| Browser Console | 0 error、0 warning | VERIFIED |
| 自动化测试 | `pytest -q`：34 passed in 1.13s | VERIFIED |

## 输出文件

- `outputs/latest/dashboard.html`
- `outputs/latest/clean_air_quality.csv`
- `outputs/latest/quality_issues.csv`
- `outputs/latest/city_summary.csv`
- `outputs/latest/monthly_summary.csv`
- `outputs/latest/report.md`

## Dashboard 内容

- Clean、城市、日期、有效 AQI、缺失记录和质量事件 KPI
- 按来源拆分的五城市 AQI 日趋势
- 五城市月均 AQI
- 城市平均 AQI
- AQI 数值区间分布
- PM2.5、PM10、NO2、O3、SO2 字段均值对比
- Clean 来源构成和质量事件分布

## 视觉修复记录

第一次 Browser 检查发现 Plotly 图表容器被 CSS Grid 压缩，主体发生裁切。增加明确图表高度、取消横向裁切并内嵌空 favicon 后，第二次桌面检查通过。窄屏首次检查发现图表过度压缩，随后改为 Panel 内横向滚动并再次通过检查。

## 证据边界

- 证明当前实际 MySQL 数据能生成可阅读、可对账的静态 Portfolio Dashboard。
- 不证明实时刷新、Web Application、预测、调度或生产发布能力。
- 污染物图表不声明现有 API 的正式单位；不同指标使用独立纵轴。
- 浏览器验收只覆盖本次本地 Chromium 环境，不代表所有浏览器和设备组合。
