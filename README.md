# 多城市空气质量 ETL Pipeline

面向 ETL、初级数据开发和数据工程实习岗位的 Python Portfolio 辅助项目。项目使用 2025 年历史 CSV 初始化北京、上海、广州、成都、武汉的数据，并通过公开空气质量接口采集后续增量，经 MySQL Raw、Clean 和质量处理形成可追溯、可重复执行的数据链路。

## 核心能力

- **API 数据采集**：限制目标域名、城市白名单、超时和响应大小，显式 `--execute` 后才联网。
- **历史数据初始化**：校验 QuotSoft 全国城市小时 CSV，提取五城市并确定性转换为日粒度记录。
- **可追溯 Raw 层**：区分历史 CSV 与 API 来源，保留来源键、观测小时、文件名、批次和 SHA-256。
- **ETL 与质量处理**：确定性解析 `/Date(...)/`，规范化污染物字段，识别缺失和越界值。
- **MySQL 幂等存储**：Raw 层按来源键 Upsert，Clean 层按 `(city, business_date)` Upsert。
- **确定性增量合并**：显式规定 API 优先于历史 CSV，并报告新增、重叠、来源变化和未变化业务键。
- **可视化交付**：输出来源分段日趋势、月度趋势、城市/污染物对比、AQI 区间、来源构成和质量事件 Dashboard。
- **自动化测试**：覆盖采集安全边界、Hash、日期解析、质量规则和报告生成。

## 数据流

```text
历史 CSV → 校验与日粒度转换 ┐
                              ├→ MySQL Raw → Clean + Quality Log
CNEMC API → Raw JSON + Manifest ┘
```

## 快速开始

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中填写项目 MySQL 账号。该账号需要对 `MYSQL_DATABASE` 中的项目自有表具备 `CREATE / SELECT / INSERT / UPDATE` 权限。

```powershell
# 创建缺失的项目表，不执行 DROP
.\.venv\Scripts\python.exe -m scripts.main init

# 显式采集五城市；真实 Raw 数据保存在 Git 忽略目录
.\.venv\Scripts\python.exe -m scripts.main collect --execute --cities 110000 310000 440100 510100 420100

# 每个 Snapshot 批次分别导入 Raw 层
.\.venv\Scripts\python.exe -m scripts.main load --batch-dir data\raw\<batch_id>

# 历史 CSV 先只读验证，再导入 Raw
.\.venv\Scripts\python.exe -m scripts.main validate-history --input-dir data\raw\history_csv\incoming
.\.venv\Scripts\python.exe -m scripts.main load-history --input-dir data\raw\history_csv\incoming

# 指定历史批次执行 Raw → Clean
.\.venv\Scripts\python.exe -m scripts.main run --batch-id history-csv-20250101-20251231

.\.venv\Scripts\python.exe -m scripts.main run
.\.venv\Scripts\python.exe -m scripts.main report --output-dir outputs\latest
```

已有旧版 `raw_air_quality` 的数据库必须先备份，并在明确授权后执行
`sql/migrations/001_add_raw_source_provenance.sql`；`init` 只创建缺失表，不会自动迁移现有表。

没有可写 MySQL 时，可以从 Snapshot 生成只读预览：

```powershell
.\.venv\Scripts\python.exe -m scripts.main preview --batch-dirs data\raw\<batch_1> data\raw\<batch_2> --output-dir outputs\preview
```

## 测试

```powershell
$env:TEMP=(Resolve-Path runtime\tmp).Path
$env:TMP=$env:TEMP
.\.venv\Scripts\python.exe -m pytest -q
```

## 当前证据边界

- `VERIFIED`：2026-10-18 五城市 Source Probe 均返回 HTTP 200，每城 14 条，共 70 条；Snapshot Hash 与 Contract 复核通过。
- `VERIFIED`：五城市 Snapshot 已生成离线 Dashboard，覆盖 2026-10-04 至 2026-10-17。
- `VERIFIED`：2025 年 365 个历史 CSV 已生成五城市 Raw/Clean 各 1,825 条；每城 365 天。
- `VERIFIED`：历史数据重复导入和 ETL 后，Raw、Clean、唯一业务键与质量事件数量均未增长。
- `VERIFIED`：全年 Dashboard 已基于 1,905 条 Clean Record 生成六类文件，月度汇总与 Clean 总数对账一致。
- `VERIFIED`：桌面与 390px 窄屏均通过 Browser 视觉检查，控制台 0 error、0 warning。
- `VERIFIED`：当前自动化测试为 34 passed。
- `VERIFIED`：MySQL 8.0.44 项目 Schema 初始化成功；五批 Raw 共 70 条导入成功。
- `VERIFIED`：2026-10-20 五城市真实增量各新增 2 天；重复执行后最终 Raw 1,905、Clean 1,905、唯一业务键 1,905、质量事件 469。
- 历史 CSV 的字段单位依据 QuotSoft 数据说明；现有 API 的正式单位仍为 `UNKNOWN`。
- 污染物正式单位仍未获得可靠接口字典证明，Dashboard 不声明具体浓度单位。

## 安全与数据边界

- `.env`、真实 Raw JSON、运行输出和本地虚拟环境不提交 Git。
- 项目只创建缺失的自有表，不执行 `DROP TABLE`，ETL 不修改 Raw 层。
- 测试 Fixture 与真实采集数据明确隔离。
- `D:\Projects\AQADR` 仅作为只读历史参考，本项目不修改或复制其环境与输出。

更多约束见 [Confirmed Spec](docs/spec.md)、[实施计划](docs/plan.md)、[当前状态](docs/status/current.md) 和 `docs/acceptance/` 下的 API、历史初始化、增量及全年 Dashboard 验收证据。
