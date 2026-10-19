# Repository Instructions

## 项目目标

将本仓库建设为可运行、可复现、可解释的多城市空气质量 Python ETL 项目，用于数据开发、数据工程和数仓开发方向的 Portfolio 展示。实现以 `docs/spec.md` 的 Confirmed Spec 为准。

## Documentation Map

- `README.md`：项目价值、证据边界和使用入口。
- `docs/spec.md`：已确认 Scope、数据 Contract、Acceptance Criteria 与变更控制。
- `docs/plan.md`：Stage 顺序、Gate 和当前 Step。
- `docs/status/current.md`：`VERIFIED / DOING / DESIGNED / HISTORY / UNKNOWN`。
- `docs/source-baseline.md`：AQADR 只读资产、来源证据、Raw Contract 和待验证边界。
- `docs/acceptance/`：仅保存实际执行产生的脱敏验收证据。

## 关键 Contract

- Raw JSON Snapshot + Manifest 是可审计的原始事实；真实 Raw 数据保存在 Git 忽略目录，只提交经检查的最小脱敏 Fixture。
- MySQL `raw_air_quality` 是可从 Snapshot 重建的结构化落地区；采集 Loader 可按确认的 Contract 受控写入，ETL 对其只读，不覆盖、不清空、不自动迁移。
- 清洗结果以 `(city,date)` 为业务唯一键；真实数据验证前不得臆定去重排序规则。
- 业务日期按 `Asia/Shanghai` 解释；`/Date(…)/` 解析必须与真实样例复核。
- 缺失处理默认策略为 `none`；填补值必须留痕，且不得冒充实测值。
- 质量日志表示历史发现事件，不等同当前未解决问题列表。
- 不得虚构接口 URL、授权、字段单位、数据量、性能或真实运行结果。

## 证据规则

- 使用 `VERIFIED / DOING / DESIGNED / HISTORY / UNKNOWN` 标记状态。
- 文件存在、静态检查、合成数据测试和历史文档不等于真实 MySQL 或端到端证明。
- 演示数据与真实数据必须隔离；报告应绑定本次实际输入、参数和输出。
- 简历只描述在本仓库实际复核并有验收证据的成果。

## 开发与安全

- 先检查 Repository、当前 Diff、Confirmed Spec 和 Documentation Map，再修改。
- AQADR 只作为只读参考；独立实现并验证必要逻辑，不修改、整理或整体迁移旧 Repository，不复制其 `.git`、`.venv`、缓存或输出目录。
- 使用清晰命名和短小函数；核心流程、业务规则、边界条件及非显然实现添加中文注释或 Docstring。
- Secret 只保存在本地 `.env`；示例配置只能使用占位值。
- 未经用户明确授权，不执行真实 Source Probe、正式采集或连接真实 MySQL，不执行 DDL、写入、迁移或数据清理。
- Verification 按 `Targeted Test → Module Test → Integration Test → Full Test Suite` 扩大，不得把未运行检查写成通过。
- 不自动 Commit、Push、Merge 或改写 Git History。
