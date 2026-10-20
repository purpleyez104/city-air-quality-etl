# 多城市空气质量 ETL Pipeline｜Confirmed Spec V2.2

> 确认日期：2026-10-20
> 定位：ETL / 初级数据开发简历的辅助 Portfolio 项目
> 开发策略：一天版增强 MVP，普通开发流程，不启用复杂 Gate

## 1. Goal

构建一个规模适中但链路完整的 Python ETL 项目，展示历史数据初始化、API 增量采集、Raw 数据追溯、MySQL 分层存储、数据质量、幂等写入、自动化测试和可视化交付能力。

本项目不替代主数据仓库项目，不承担 Spark/Hive、维度建模或海量数据处理能力证明。

## 2. Users / Use Cases

- 项目作者通过统一 CLI 采集、导入、清洗并生成报告。
- 招聘者通过 README、代码、测试和 Dashboard 理解项目的数据链路与工程能力。
- 面试中可以解释来源追溯、质量规则、业务唯一键和幂等实现。

## 3. Scope

- 城市：北京、上海、广州、成都、武汉。
- 粒度：每城市每天一条 Clean Record。
- 来源：QuotSoft 全国城市历史 CSV，以及现有 CNEMC 候选 API。
- 链路：历史 CSV / API Snapshot → MySQL Raw → Clean + Quality Log → 静态 Dashboard；历史初始化 Stage 只新增 Raw/Clean，展示 Stage 复用统一 Clean Contract。
- 质量规则：缺失、非数值、越界、未知城市、非法日期和重复业务键。
- 输出：Clean CSV、Quality CSV、City Summary、Markdown Report、HTML Dashboard。
- Dashboard 输出来源分段日趋势、月度趋势、城市对比、AQI 数值区间、主要污染物字段、来源构成和质量事件；同时生成 `monthly_summary.csv`。
- 验证：Targeted Tests、五城市最小 Source Probe、MySQL 小批次与重复执行。

## 4. Non-goals

不开发 Airflow、Kafka/Flink、Spark/Hive、Web Server、账户系统、Docker/Kubernetes、CI/CD、预测模型、自动异常修复和生产监控。

## 5. Key Contracts

### 5.1 Raw Contract

- 每次成功请求保存原始响应正文，不在落盘前修改字段。
- Manifest 记录 `batch_id`、请求时间、城市、状态、记录数、字节数、文件名和 SHA-256。
- 历史 CSV 原文件保持不变；Loader 校验 UTF-8、Header、日期、小时、指标和五城市列后再转换。
- MySQL Raw 使用 `source_type / source_record_key` 区分来源，并保留 `observation_hour / source_file`。
- 真实 Raw 数据保存在 Git 忽略目录，只提交脱敏最小 Fixture。
- 响应校验失败时不生成成功 Snapshot。

### 5.2 Data Contract

- Canonical 数值字段：`aqi / pm10 / pm2_5 / so2 / co / no2 / o3`。
- `/Date(epoch_ms)/` 按固定 UTC+08:00 转换为业务日期，不依赖主机时区。
- 历史 CSV 每日固定优先选择 `23:00`；该小时的 Canonical 指标行整体不存在时，回退到当天最晚可用小时并记录实际 `observation_hour`。
- 历史字段映射使用 `AQI / PM10_24h / PM2.5_24h / SO2_24h / CO_24h / NO2_24h / O3_8h_24h`。
- Clean 业务唯一键为 `(city, business_date)`。
- 同一业务键存在多个来源时显式使用 `cnemc_api > quotsoft_history_csv`；不得依赖 `source_id` 大小或输入顺序表达优先级。
- 同一来源内按来源时间点、稳定来源键和 Raw ID 确定性排序；未知 `source_type` 拒绝进入 Clean。
- 缺失值默认不填补；越界值在 Clean 层置为 `NULL`，Raw 层保留原值。
- 历史 CSV 单位只按 QuotSoft 数据说明解释；不得外推为现有 API 的正式字段字典。
- Dashboard 不填充缺失值；聚合只使用对应字段有效样本，并同时展示有效样本、缺失记录和质量事件数量。
- 历史 CSV 与 API 使用独立趋势 Trace，时间断档不得表现为连续观测。

### 5.3 MySQL Contract

- `raw_air_quality`：结构化 Raw 层，ETL 只读。
- `air_quality`：日粒度 Clean 层，按业务键幂等 Upsert。
- `air_quality_quality_log`：稳定 `issue_key` 的历史质量事件。
- `air_quality_etl_runs`：记录每次运行的状态与数量。
- 初始化只使用 `CREATE TABLE IF NOT EXISTS`，不执行 `DROP`、清空或自动迁移。
- 已存在数据库的来源字段变化通过单独 Migration 执行，必须明确授权且执行前备份。

## 6. CLI

```text
init       创建缺失的项目表
collect    显式授权后采集一个或多个城市
load       校验并导入一个 Snapshot 批次
validate-history  校验并转换历史 CSV，不连接数据库
load-history      校验历史 CSV 并幂等导入 Raw
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
- **AC-09**：365 个历史 CSV 能确定性生成五城市 2025 年日粒度 Raw/Clean Record。
- **AC-10**：历史批次重复导入和 ETL 后，Raw、Clean、业务键与质量事件数量不增长。
- **AC-11**：API 增量能报告新增、重叠、来源变化与未变化业务键，并在重复执行后保持幂等。
- **AC-12**：全年 Dashboard 能由真实 MySQL 数据生成六类输出，月度统计与 Clean 对账一致，并通过 Browser 视觉检查。

## 8. Evidence Status

- `VERIFIED`：AC-01 至 AC-12；历史初始化、五城市 API 增量和全年 Dashboard 均已完成实际验收。
- `VERIFIED`：34 项自动化测试通过；Runtime 证据见 `docs/acceptance/` 下三份当前验收记录。
- `VERIFIED` 与 `UNKNOWN` 的详细边界以 `docs/status/current.md` 为准。

## 9. Decisions

- 采用 MySQL 而非 SQLite，增强 ETL 岗位相关性。
- 使用 Plotly 静态 HTML，而非开发 Web Application。
- 仅从全国历史数据中提取五城市 2025 年记录，以小范围完整链路替代全城市扩张。
- 历史初始化 Stage 只建设 Raw/Clean，不新增调度、缺失值填充或独立分析层；Dashboard 由后续展示 Stage 基于统一 Clean 数据生成。
- API 与历史 CSV 的来源优先级使用显式映射；新增来源必须登记优先级后才能进入 Clean。
- 全年 Dashboard 保持静态 HTML + CSV/Markdown 交付，不扩展为 Web Application。
- 只实现对简历声明有直接证明力的测试，不追求形式化 Gate 或覆盖率指标。
