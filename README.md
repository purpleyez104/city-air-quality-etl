# 多城市空气质量 ETL Pipeline

面向 ETL、初级数据开发和数据工程实习岗位的 Python Portfolio 辅助项目。项目从公开空气质量接口采集北京、上海、广州、成都、武汉的日粒度数据，经 Raw Snapshot、MySQL 原始层、质量清洗与幂等 Upsert，最终生成 CSV、Markdown 和 Plotly Dashboard。

## 核心能力

- **API 数据采集**：限制目标域名、城市白名单、超时和响应大小，显式 `--execute` 后才联网。
- **可追溯 Raw 层**：原始 JSON 与 Manifest 原子落盘，记录批次、字节数和 SHA-256。
- **ETL 与质量处理**：确定性解析 `/Date(...)/`，规范化污染物字段，识别缺失和越界值。
- **MySQL 幂等存储**：Raw 层按来源键 Upsert，Clean 层按 `(city, business_date)` Upsert。
- **可视化交付**：输出五城市 AQI 趋势、城市对比和质量问题分布 Dashboard。
- **自动化测试**：覆盖采集安全边界、Hash、日期解析、质量规则和报告生成。

## 数据流

```text
CNEMC API → Raw JSON + Manifest → MySQL Raw → Clean + Quality Log → Dashboard
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

.\.venv\Scripts\python.exe -m scripts.main run
.\.venv\Scripts\python.exe -m scripts.main report --output-dir outputs\latest
```

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
- `VERIFIED`：当前自动化测试为 27 passed。
- `VERIFIED`：MySQL 8.0.44 项目 Schema 初始化成功；五批 Raw 共 70 条导入成功。
- `VERIFIED`：连续执行两次 ETL 后，Raw 70、Clean 70、唯一业务键 70、质量问题 0，数据库幂等核验通过。
- 污染物正式单位仍未获得可靠接口字典证明，Dashboard 不声明具体浓度单位。

## 安全与数据边界

- `.env`、真实 Raw JSON、运行输出和本地虚拟环境不提交 Git。
- 项目只创建缺失的自有表，不执行 `DROP TABLE`，ETL 不修改 Raw 层。
- 测试 Fixture 与真实采集数据明确隔离。
- `D:\Projects\AQADR` 仅作为只读历史参考，本项目不修改或复制其环境与输出。

更多约束见 [Confirmed Spec](docs/spec.md)、[实施计划](docs/plan.md)、[当前状态](docs/status/current.md) 和 [MySQL 验收证据](docs/acceptance/2026-10-18-mysql-etl.md)。
