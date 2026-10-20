# 历史 CSV Raw/Clean 验收证据

> 执行日期：2026-10-20（Asia/Shanghai）  
> 数据库：本地 MySQL 8.0.44，项目库 `city_air_quality_etl`  
> 来源：https://quotsoft.net/air/  
> Secret：未记录密码或完整连接字符串

## Acceptance → Evidence

| Acceptance | 实际证据 | 状态 |
| --- | --- | --- |
| 历史文件校验 | 365 个 UTF-8 CSV，统一 378 列，覆盖 `2025-01-01`～`2025-12-31` | VERIFIED |
| 五城市日粒度转换 | 北京、上海、广州、成都、武汉各 365 条，共 1,825 条 | VERIFIED |
| 固定小时与回退 | 默认 23 时；20 条因该小时指标行不存在而使用更早小时 | VERIFIED |
| 缺失值边界 | 67 条 Clean Record 含缺失，共 469 个 `MISSING` 事件；未填充 | VERIFIED |
| Raw 来源追踪 | `source_type / source_record_key / observation_hour / source_file` 已写入 | VERIFIED |
| Raw/Clean MySQL | 历史 Raw 1,825、历史 Clean 1,825 | VERIFIED |
| 业务键唯一 | 最终 Clean 1,895，唯一 `(city,business_date)` 1,895 | VERIFIED |
| 两次幂等执行 | 第二次执行后 Raw 1,895、Clean 1,895、质量事件 469，均未增长 | VERIFIED |
| 自动化测试 | `pytest -q`：31 passed | VERIFIED |

## 数据集证据

- Batch：`history-csv-20250101-20251231`
- 原始 CSV 总大小：136,564,155 bytes
- 数据集整体 SHA-256：`ef9234d670e85c9751f36913cc141f2caabc98b0bd924b5ceb94c1617ecbc406`
- Raw 总数：1,895，其中历史 CSV 1,825、原 API 70
- Clean 总数：1,895
- Quality Log：469，均为历史字段缺失

## 两次历史 ETL Run

- Run 1：`c06d3629-e425-42e7-84c5-ecab3fc4d4fc`
- Run 2：`2646002b-9f8a-4e28-828b-3544b7e7faeb`

每次运行均读取 1,825 条历史 Raw，对 1,825 个 Clean 业务键和 469 个稳定质量事件执行 Upsert。CLI 的 `upserted_count` 表示参与 Upsert 的记录数，不表示新增行数。

## 证据边界

- 证明当前 2025 年历史 CSV 可以在本地 MySQL 完成 Raw/Clean 初始化与重复执行。
- 不证明 QuotSoft 数据具有开放再分发 License、现有 API 长期稳定或大规模性能。
- QuotSoft 页面中的历史 CSV 单位说明不能外推为现有 API 的正式字段字典。
- Raw CSV、数据库备份和运行输出保持 Git Ignore；本文只保存脱敏摘要。
