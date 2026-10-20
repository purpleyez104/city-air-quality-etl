# 项目设计

## 项目目标

这是一个面向数据开发和数据工程岗位的 Python ETL 项目。项目使用历史 CSV 初始化数据，再通过 API 追加近期数据，展示数据采集、来源追踪、MySQL 分层存储、质量检查、幂等写入、自动化测试和可视化输出。

项目只处理北京、上海、广州、成都和武汉五个城市，不引入调度平台、实时计算框架、分布式存储、预测模型或 Web 服务。

## 数据流程

```text
QuotSoft 历史 CSV ─┐
                    ├─→ MySQL Raw ─→ Clean + Quality Log ─→ CSV / Markdown / Dashboard
CNEMC API Snapshot ─┘
```

Clean 层保持每个城市每天一条记录，业务唯一键为 `(city, business_date)`。主要数值字段为 `aqi`、`pm10`、`pm2_5`、`so2`、`co`、`no2` 和 `o3`。

## 数据处理规则

### 历史 CSV

- 原文件不做修改，导入前检查 UTF-8 编码、表头、日期、小时、指标名称和五城市列。
- 每天优先使用 `23:00` 的数据；如果该小时没有任何目标指标，则使用当天最晚的可用小时，并记录实际小时。
- 字段映射为 `AQI / PM10_24h / PM2.5_24h / SO2_24h / CO_24h / NO2_24h / O3_8h_24h`。
- 缺失值保留为 `NULL`，不使用其他小时或统计值填充。

### API 数据

- 成功响应保存为原始 JSON，并生成包含批次、城市、记录数、字节数和 SHA-256 的 Manifest。
- `/Date(epoch_ms)/` 固定按 UTC+08:00 转换为业务日期，不依赖运行机器的本地时区。
- 只有通过格式和字段检查的响应才能进入 MySQL Raw 层。

### 来源合并和质量检查

- Raw 层使用 `source_type` 和 `source_record_key` 区分并追踪不同来源。
- 当同一城市和日期同时存在 API 与历史 CSV 数据时，优先使用 API 数据。
- 同一来源内按数据时间、来源键和 Raw ID 排序，保证重复执行得到相同结果。
- 缺失值记录 `MISSING` 事件；负值以及超过 500 的 AQI 记为越界并在 Clean 层置为 `NULL`。Raw 层始终保留原值。
- Dashboard 聚合时只计算有效样本，历史 CSV 与 API 使用不同曲线，避免跨时间空档连线。

## MySQL 表

- `raw_air_quality`：保存可追溯的结构化原始数据。
- `air_quality`：保存日粒度清洗结果，按业务键执行 Upsert。
- `air_quality_quality_log`：保存稳定编号的质量问题。
- `air_quality_etl_runs`：记录每次 ETL 的执行状态和数量。

初始化只创建不存在的表，不会删除、清空或自动迁移已有表。旧数据库需要增加来源字段时，应先备份，再单独执行 `sql/migrations/001_add_raw_source_provenance.sql`。

## 命令行入口

```text
init              创建缺失的项目表
collect           采集一个或多个城市
load              导入 API Snapshot
validate-history  校验并转换历史 CSV，不连接数据库
load-history      校验历史 CSV 并导入 Raw 层
run               执行 Raw 到 Clean 的 ETL
report            从 MySQL 生成报告
preview           从 Snapshot 生成不写数据库的预览
```

## 完成标准

- 五城市 API 响应可以保存、校验并重复导入。
- 365 个历史 CSV 可以生成五城市 2025 年日粒度数据。
- 相同数据重复执行后，Raw、Clean、业务键和质量问题数量不增长。
- API 增量能够区分新增、重叠和来源变化。
- Dashboard、CSV 和 Markdown 由实际 MySQL 数据生成，月度统计能与 Clean 层对账。
- 核心测试通过，运行命令可复现，仓库不包含密码和真实 Raw 数据。

当前项目已经达到以上标准，具体数字和测试结果见 [验证记录](validation.md)。
