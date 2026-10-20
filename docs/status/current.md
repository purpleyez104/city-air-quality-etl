# 当前状态

> 更新时间：2026-10-20（Asia/Shanghai）

## VERIFIED

- 2026-10-18 五城市 Source Probe 均返回 HTTP 200 和 14 条记录，共 70 条；Raw JSON、Manifest、SHA-256 与响应 Contract 已复核。
- 原 API 数据覆盖 `2026-10-04`～`2026-10-17`，已完成 MySQL Raw/Clean、两次幂等 ETL 和 Dashboard 验收。
- QuotSoft 2025 年历史数据共 365 个有效 CSV、136,564,155 bytes，覆盖 `2025-01-01`～`2025-12-31`。
- 历史 Loader 已验证 UTF-8、统一 378 列、文件日期、小时、Canonical 指标和五城市字段，并自动忽略 `._*` 元数据文件。
- 历史数据生成 Raw/Clean 各 1,825 条，每个城市 365 条；20 条使用更早小时回退。
- 历史 Clean 中 67 条 Record 含缺失值，共产生 469 个 `MISSING` 事件；没有执行缺失值填充。
- 历史批次连续执行两次 Raw Upsert 和 Clean ETL 后，Raw、Clean、唯一业务键与质量事件数量均未增长。
- 2026-10-20 五城市再次 Probe 均为 HTTP 200、每城 14 条；相对原 API 基线每城新增 `2026-10-18` 和 `2026-10-19` 两天。
- 第一次增量 ETL 每城 `new=2 / overlap=12 / changed_source=0 / unchanged_source=12`；第二次每城 `new=0 / overlap=14 / unchanged_source=14`。
- 最终 MySQL 8.0.44 状态：Raw 1,905、Clean 1,905、唯一 `(city,business_date)` 1,905、质量事件 469、成功运行 14 次。
- API Raw 80 条，覆盖 `2026-10-04`～`2026-10-19`；历史 Raw 1,825 条，覆盖完整 2025 年。
- 全年报告已由真实 MySQL 数据生成：Clean 1,905、五城市、日期 `2025-01-01`～`2026-10-19`、AQI 有效样本 1,838、含缺失记录 67、质量事件 469。
- `monthly_summary.csv` 共 65 行（13 个月 × 5 城市），`record_count` 合计 1,905，与 Clean 完全一致。
- Dashboard 包含七张图表；历史 CSV 与 API 使用独立 Trace，缺失值未填充，各指标聚合只使用有效样本。
- Browser 实际检查覆盖桌面和 390px 窄屏：图表完整渲染、页面无整体横向溢出、窄屏图表可在 Panel 内滚动、控制台 0 error/0 warning。
- 本次文档同步复验结果为 `34 passed in 1.08s`；`compileall` 与 `git diff --check` 通过。

## UNKNOWN

- 现有 API 污染物字段的正式单位；QuotSoft 的历史 CSV 单位说明不得直接外推到 API。
- 候选 API 的长期稳定性和访问限制。
- QuotSoft 页面允许分析、研究，但未发现明确的开源再分发 License；Raw CSV 保持 Git Ignore。

## HISTORY

- 初次验收时只读账号执行 DDL 返回 MySQL 1142；随后使用项目 `.env` 中的可写账号完成验收。
- 2026-10-20 执行 Raw 来源字段 Migration 前，已将原 70 条 Raw 和建表语句备份到 Git 忽略的 `runtime/backups/`。

## 下一入口

历史初始化、API 增量衔接和全年 Dashboard 均已完成。重新验证历史数据可执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.main validate-history --input-dir data\raw\history_csv\incoming
.\.venv\Scripts\python.exe -m scripts.main load-history --input-dir data\raw\history_csv\incoming
.\.venv\Scripts\python.exe -m scripts.main run --batch-id history-csv-20250101-20251231
```

历史初始化、API 增量衔接和全年 Dashboard 均已完成。下一实质功能必须先确认新的 Stage Scope；当前没有阻塞性交付项。
