# 多城市空气质量 ETL Pipeline｜Confirmed Spec V2.0

> 确认日期：2026-10-18  
> 定位：ETL / 初级数据开发简历的辅助 Portfolio 项目  
> 开发策略：一天版增强 MVP，普通开发流程，不启用复杂 Gate

## 1. Goal

构建一个规模适中但链路完整的 Python ETL 项目，展示 API 数据采集、Raw 数据追溯、MySQL 分层存储、数据质量、幂等写入、自动化测试和可视化交付能力。

本项目不替代主数据仓库项目，不承担 Spark/Hive、维度建模或海量数据处理能力证明。

## 2. Users / Use Cases

- 项目作者通过统一 CLI 采集、导入、清洗并生成报告。
- 招聘者通过 README、代码、测试和 Dashboard 理解项目的数据链路与工程能力。
- 面试中可以解释来源追溯、质量规则、业务唯一键和幂等实现。

## 3. Scope

- 城市：北京、上海、广州、成都、武汉。
- 粒度：每城市每天一条 Clean Record。
- 链路：API → Raw JSON + Manifest → MySQL Raw → Clean + Quality Log → Dashboard。
- 质量规则：缺失、非数值、越界、未知城市、非法日期和重复业务键。
- 输出：Clean CSV、Quality CSV、City Summary、Markdown Report、HTML Dashboard。
- 验证：Targeted Tests、五城市最小 Source Probe、MySQL 小批次与重复执行。

## 4. Non-goals

不开发 Airflow、Kafka/Flink、Spark/Hive、Web Server、账户系统、Docker/Kubernetes、CI/CD、预测模型、自动异常修复和生产监控。

## 5. Key Contracts

### 5.1 Raw Contract

- 每次成功请求保存原始响应正文，不在落盘前修改字段。
- Manifest 记录 `batch_id`、请求时间、城市、状态、记录数、字节数、文件名和 SHA-256。
- 真实 Raw 数据保存在 Git 忽略目录，只提交脱敏最小 Fixture。
- 响应校验失败时不生成成功 Snapshot。

### 5.2 Data Contract

- Canonical 数值字段：`aqi / pm10 / pm2_5 / so2 / co / no2 / o3`。
- `/Date(epoch_ms)/` 按固定 UTC+08:00 转换为业务日期，不依赖主机时区。
- Clean 业务唯一键为 `(city, business_date)`。
- 缺失值默认不填补；越界值在 Clean 层置为 `NULL`，Raw 层保留原值。
- 未确认污染物正式单位前，报告和简历不声明具体单位。

### 5.3 MySQL Contract

- `raw_air_quality`：结构化 Raw 层，ETL 只读。
- `air_quality`：日粒度 Clean 层，按业务键幂等 Upsert。
- `air_quality_quality_log`：稳定 `issue_key` 的历史质量事件。
- `air_quality_etl_runs`：记录每次运行的状态与数量。
- 初始化只使用 `CREATE TABLE IF NOT EXISTS`，不执行 `DROP`、清空或自动迁移。

## 6. CLI

```text
init       创建缺失的项目表
collect    显式授权后采集一个或多个城市
load       校验并导入一个 Snapshot 批次
run        执行 Raw 到 Clean 的 ETL
report     从 MySQL Clean 层生成报告
preview    从 Snapshot 生成不写数据库的预览
```

## 7. Acceptance Criteria

- **AC-01**：五城市请求均能生成可校验 Snapshot 与 Manifest。
- **AC-02**：Snapshot Hash、记录数和响应结构复核一致。
- **AC-03**：项目四张 MySQL 表能以非破坏方式初始化。
- **AC-04**：五城市 Raw Record 能幂等导入。
- **AC-05**：ETL 能生成唯一的 `(city, business_date)` Clean Record 和质量事件。
- **AC-06**：同一输入重复运行后业务键数量和质量问题键集合不变。
- **AC-07**：Dashboard、CSV 和 Markdown 能由本次实际输入生成。
- **AC-08**：核心自动化测试通过，README 命令可复现，仓库不包含 Secret。

## 8. Evidence Status

- `VERIFIED`：AC-01 至 AC-08；五城市 70 条真实数据已完成 Snapshot、MySQL Raw、Clean Upsert、两次幂等运行与 Dashboard 验收。
- `VERIFIED`：27 项自动化测试通过；MySQL Runtime 证据见 `docs/acceptance/2026-10-18-mysql-etl.md`。
- `VERIFIED` 与 `UNKNOWN` 的详细边界以 `docs/status/current.md` 为准。

## 9. Decisions

- 采用 MySQL 而非 SQLite，增强 ETL 岗位相关性。
- 使用 Plotly 静态 HTML，而非开发 Web Application。
- 采用五城市小时间窗口，而非追求大量历史数据。
- 只实现对简历声明有直接证明力的测试，不追求形式化 Gate 或覆盖率指标。
