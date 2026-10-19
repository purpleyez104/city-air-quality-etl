# 当前状态

> 更新时间：2026-10-18（Asia/Shanghai）

## VERIFIED

- 五城市 Source Probe 于 2026-10-18 成功执行：北京、上海、广州、成都、武汉均返回 HTTP 200 和 14 条记录，共 70 条。
- 五个 Raw JSON Snapshot 与 Manifest 已原子落盘，SHA-256、记录数和响应 Contract 复核通过。
- 实际数据业务日期覆盖 2026-10-04 至 2026-10-17，每城 14 条。
- Raw Loader、字段规范化、固定 UTC+08:00 日期解析、质量规则、MySQL Repository、ETL Runner、统一 CLI 和 Plotly Dashboard 已实现。
- 五城市实际 Snapshot 已生成离线预览：70 条 Clean Record、5 个城市、当前规则下 0 条质量问题。
- `pytest -q` 实际结果为 `27 passed in 1.09s`。
- MySQL 8.0.44 项目 Schema 已通过 `CREATE TABLE IF NOT EXISTS` 初始化。
- 五个 Snapshot 共 70 条记录已导入 `raw_air_quality`。
- ETL 连续执行两次均成功；最终 `raw=70`、`clean=70`、唯一 `(city,business_date)=70`、质量问题 `0`、成功运行记录 `2`。
- 数据库结果已生成 `outputs/latest` 下的 Dashboard、Clean CSV、Quality CSV、City Summary 和 Markdown Report。

## UNKNOWN

- 污染物字段的正式单位；当前报告不声明单位。
- 候选接口的长期稳定性和访问限制。

## HISTORY

- 初次验收时环境只有只读账号，执行 DDL 返回 MySQL 1142。
- 用户随后在项目 `.env` 配置可写账号，项目代码通过 PyMySQL 完成当前验收；运行不依赖 DBHub。

## 下一入口

项目当前实现与验收已完成。后续重新采集数据时依次执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.main init
.\.venv\Scripts\python.exe -m scripts.main load --batch-dir data\raw\<batch_id>
.\.venv\Scripts\python.exe -m scripts.main run
.\.venv\Scripts\python.exe -m scripts.main report --output-dir outputs\latest
```
