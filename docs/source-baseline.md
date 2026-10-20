# 数据来源基线

> 状态：AQADR 只读盘点、五城市 Source Probe 与 2025 年历史 CSV 验收已完成。
> 盘点与复核日期：2026-10-15～2026-10-20（Asia/Shanghai）

## 当前结论

AQADR 只作为当前项目的只读参考。项目以 QuotSoft 2025 年 CSV 初始化历史数据，并使用现有 CNEMC 候选 API 采集后续增量。2026-10-18 的五城市 Probe 共返回 70 条；2026-10-20 的历史批次生成五城市日记录 1,825 条。两类来源在 MySQL Raw 中通过稳定来源键区分，证据边界分别记录。

## QuotSoft 历史 CSV 来源

- 页面：https://quotsoft.net/air/
- 页面说明全国城市数据来自中国环境监测总站，全国数据自 2014-05-13 起提供，并可能因服务器或来源问题出现缺失。
- `china_cities_YYYYMMDD.csv` 是城市平均数据；结构为 `date / hour / type / 各城市`，采用 UTF-8。
- 页面列出了 AQI、小时均值、24 小时均值以及 O3 8 小时滑动均值等数据类型和单位。
- 页面欢迎分析、研究，但未发现明确的开源再分发 License；真实 CSV 只保存在 Git 忽略目录。

### 2025 年数据复核

- 365 个有效 CSV，136,564,155 bytes，日期连续覆盖 `2025-01-01`～`2025-12-31`。
- 文件统一为 378 列，五城市字段存在；另有两个 `._*` 元数据文件，Loader 自动忽略。
- 数据集整体 SHA-256：`ef9234d670e85c9751f36913cc141f2caabc98b0bd924b5ceb94c1617ecbc406`。
- 日粒度固定优先选择 23 时；23 时 Canonical 指标行整体不存在时回退到当天最晚可用小时。
- 转换后五城市各 365 条，共 1,825 条；20 条发生小时回退，469 个字段保持缺失。

## AQADR 只读资产

- 路径：`D:\Projects\AQADR`。
- Git：独立 Repository，当前 Working Tree 包含 staged、unstaged 与 untracked 内容；盘点期间未修改。
- 采集器：包含五城市行政代码、历史请求 URL、POST 表单、`Referer`、30 秒超时和历史响应字段映射。
- 日期适配：包含从 `/Date(毫秒时间戳)/` 提取时间的实现，但使用主机本地时区；实际北京响应确认仍使用 `/Date(毫秒时间戳)/`，未携带显式 `+0800` 后缀。
- 数据库：存在环境变量连接方式和历史建表 SQL；建表 SQL 含破坏性 `DROP TABLE`，不得用于新项目。
- ETL：旧主流程会覆盖写入结果表，并默认修复缺失和异常，与 V1.2 Contract 不一致。
- 测试：目录中发现 6 个测试方法；旧 `.venv` 绑定到已不存在的 Python 3.9，当前系统 Python 未安装 `pandas`，因此测试未执行。
- 数据：未发现 CSV、JSON、SQL Dump、脱敏响应样例或真实输出。

## 可参考与不可直接复用

| 资产 | 处理方式 | 原因 |
| --- | --- | --- |
| 五城市代码 | 参考后重新验证 | 低成本复用，但仍需核对城市返回值 |
| 请求结构、`Referer`、字段名 | 用于最小 Source Probe | 旧接口无当前公开文档证据 |
| 日期解析思路 | 独立实现并显式使用 `Asia/Shanghai` | 旧实现依赖主机本地时区 |
| `DATABASE_URL` 配置方式 | 参考 | 当前工作树已避免源码硬编码凭据 |
| AQADR `.git`、`.venv`、缓存、输出目录 | 不复制 | 旧环境不可复现，且不属于新项目源码 |
| 破坏性建表 SQL | 不复用 | 会删除 `raw_air_quality` |
| 覆盖写表和自动异常修复逻辑 | 不复用 | 违反幂等 Upsert、默认不填补和软高值保留 Contract |

## 当前官方来源证据

截至 2026-10-16，中国环境监测总站官网仍公开城市空气质量日报、小时数据和实时数据：

- https://www.cnemc.cn/
- https://www.cnemc.cn/sssj/

官网只能证明官方数据发布渠道存在。2026-10-16 的北京 Probe 首次证明候选接口可用；2026-10-18 的五城市 Probe 又证明五城在本次请求中保持相同必要字段 Contract。以上证据仍不能证明接口长期可用、访问限制或字段正式单位。

### 2026-10-18 五城市复核

- 北京、上海、广州、成都、武汉分别请求一次，均为 HTTP 200。
- 每城市 14 条，共 70 条，业务日期覆盖 `2026-10-04`～`2026-10-17`。
- 五个 Raw JSON 与 Manifest 的 SHA-256、记录数和必要字段均复核通过。
- 实际 Snapshot 保存在 Git 忽略目录，不在文档中公开完整响应。

### 2026-10-20 五城市增量复核

- 五城市分别请求一次，均为 HTTP 200 和 14 条，共 70 条。
- 每城市相对原 Clean 基线新增 `2026-10-18`、`2026-10-19` 两个业务日期，另有 12 个重叠日期。
- 第一次增量每城 `new=2 / overlap=12 / unchanged_source=12`；重复执行每城 `new=0 / overlap=14 / unchanged_source=14`。
- API Raw 最终 80 条，覆盖 `2026-10-04`～`2026-10-19`；Quality Log 没有因本批次增长。

## 北京 Source Probe 证据

- 授权范围：仅北京 `110000`、一次 HTTPS POST；未请求其他城市，未连接 MySQL。
- 请求时间：`2026-10-16T02:53:22.710215Z`。
- 批次：`20261016T025322Z-a7eda4f2`。
- 响应：HTTP 200，`application/json; charset=utf-8`，6086 bytes，14 条记录。
- SHA-256：`9305541571a26e4249904b0cb502a139a4774f6edc7cb9f6c8805fe15de78857`；Manifest 与本地复算一致。
- 城市：`Area=北京市`、`CityCode=110000`。
- 日期：`TimePoint` 为 `/Date(毫秒时间戳)/`；按 UTC+08:00 解释后覆盖 `2026-10-02`～`2026-10-15`，共 14 个唯一业务日期。
- 追溯：14 个来源 `Id` 均唯一，未发现 `(Area, TimePoint)` 重复。
- 顺序：上游响应不是按业务日期排序，任何解析、去重或导入逻辑都不得依赖输入顺序。
- 字段共 16 个：`Id`、`CityCode`、`TimePoint`、`TimePointStr`、`Area`、`AQI`、`PM10_24h`、`PM2_5_24h`、`SO2_24h`、`CO_24h`、`NO2_24h`、`O3_8h_24h`、`PrimaryPollutant`、`Quality`、`Unheathful`、`Measure`。
- `Measure` 的实际内容是人群活动建议，不是污染物单位；字段单位仍为 `UNKNOWN`。

## 已确认 Raw Contract

- 每个成功采集批次按城市保存不可变 UTF-8 Raw JSON。
- Manifest 至少记录批次、请求时间、城市代码、脱敏请求元数据、HTTP 状态、相对路径、字节数和 SHA-256。
- Raw JSON 是原始事实，MySQL `raw_air_quality` 是可从 Snapshot 重建的结构化落地区。
- 真实 Raw 数据默认不进入 Git；只允许经过检查的最小脱敏 Fixture 入库用于测试。
- 非 JSON、字段不完整、超限或失败响应不能登记为成功 Snapshot，也不能进入 MySQL。
- 历史 CSV 保持原样；Loader 在写入前校验编码、Header、文件日期、小时、指标和目标城市。
- MySQL Raw 通过 `source_type / source_record_key` 幂等区分 CSV 与 API，并记录 `observation_hour / source_file`。
- 历史 CSV 的空值不跨小时填充；Clean 保持 `NULL` 并生成稳定 `MISSING` 事件。

## 安全发现

AQADR 的已提交历史版本中存在明文数据库连接凭据。盘点与本文均不复述该值。如果凭据曾真实使用或复用，应视为可能泄露并轮换；新项目只允许通过本地环境变量提供 Secret。

## 下一验证入口

如果未来 API 数据与历史 CSV 日期重叠，应使用专门 Fixture 和 MySQL Integration Test 验证来源优先级；当前 2025 历史数据与 2026 API 数据没有日期重叠。API 字段单位继续保持 `UNKNOWN`。
