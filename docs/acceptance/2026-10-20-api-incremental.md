# 五城市 API 增量 Raw/Clean 验收证据

> 执行日期：2026-10-20（Asia/Shanghai）  
> 数据库：本地 MySQL 8.0.44，项目库 `city_air_quality_etl`  
> Secret：未记录密码或完整连接字符串

## Acceptance → Evidence

| Acceptance | 实际证据 | 状态 |
| --- | --- | --- |
| 五城市真实采集 | 北京、上海、广州、成都、武汉均返回 HTTP 200，每城 14 条 | VERIFIED |
| Snapshot 可追溯 | 每批均保存 Raw JSON、Manifest、记录数、字节数和 SHA-256 | VERIFIED |
| 显式来源优先级 | `cnemc_api > quotsoft_history_csv`，不依赖 `source_id` 或输入顺序 | VERIFIED |
| 第一次增量 | 每城新增 2 个业务键、重叠 12 个、来源未变化 12 个 | VERIFIED |
| 第二次增量 | 每城新增 0、重叠 14、来源未变化 14 个 | VERIFIED |
| Raw 幂等 | API Raw 最终 80 条，来源键唯一 80 条 | VERIFIED |
| Clean 幂等 | 最终 Clean 1,905，唯一业务键 1,905 | VERIFIED |
| 质量事件幂等 | Quality Log 保持 469，新增 API 批次未产生质量事件 | VERIFIED |
| 自动化测试 | `pytest -q`：34 passed | VERIFIED |

## 五城市 Batch

- 北京：`20261020T070925Z-1bf9e0c6`
- 上海：`20261020T070925Z-e15cf88c`
- 广州：`20261020T070926Z-f6775dbb`
- 成都：`20261020T070926Z-e754acf8`
- 武汉：`20261020T070927Z-b267d564`

五个 Snapshot 合计 70 条，其中 60 条与已有 API Clean 业务日期重叠，10 条对应五城市的 `2026-10-18`、`2026-10-19` 新业务键。重叠记录沿用相同 `source_raw_id`，因此没有来源替换。

## 最终数据库状态

- Raw：1,905，唯一来源键 1,905
- API Raw：80，覆盖 `2026-10-04`～`2026-10-19`
- 历史 CSV Raw：1,825，覆盖 `2025-01-01`～`2025-12-31`
- Clean：1,905，唯一 `(city,business_date)` 1,905
- Quality Log：469
- Success ETL Runs：14，其中本次增量两轮共 10 次

## 证据边界

- 真实 Runtime 证明当前五城市 API 批次可以在历史初始化后增量写入并幂等重放。
- 真实数据没有与 2025 历史 CSV 日期重叠；API 优先于历史 CSV 的冲突场景由 Pipeline Integration Fixture 验证。
- 不证明 API 长期稳定、调度运行、历史 CSV 再分发权或大规模性能。
