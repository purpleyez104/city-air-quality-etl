# 数据来源基线

> 状态：AQADR 只读盘点与五城市最小 Source Probe 已完成；不代表长期接口稳定性、字段正式单位或 MySQL 已验收。  
> 盘点与复核日期：2026-10-15～2026-10-18（Asia/Shanghai）

## 当前结论

AQADR 只作为当前项目的只读参考。历史 MySQL 数据已因本地数据库重装而丢失，当前项目采用 Raw JSON + MySQL 双层 Raw Baseline。2026-10-18 经明确授权完成北京、上海、广州、成都、武汉五次最小 Source Probe：均返回 HTTP 200 和 14 条记录，共 70 条，五个 Snapshot 的 Manifest、SHA-256、记录数和必要字段 Contract 均已复核。该结果只证明本次请求成功，不能外推为完整历史范围、长期稳定性或正式字段单位证明。

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

## 安全发现

AQADR 的已提交历史版本中存在明文数据库连接凭据。盘点与本文均不复述该值。如果凭据曾真实使用或复用，应视为可能泄露并轮换；新项目只允许通过本地环境变量提供 Secret。

## 下一验证入口

1. 仅使用已保存的北京 Snapshot 建立显式字段映射与规范化记录，不再请求接口。
2. 独立实现 `/Date(...)` 到 UTC+08:00 业务日期的确定性解析，不依赖主机本地时区或响应顺序。
3. 明确来源 `Id`、`CityCode`、`Area`、`TimePoint` 的追溯语义，并形成 MySQL 导入幂等键候选方案。
4. 保持字段单位为 `UNKNOWN`，直到获得可靠来源字典或官方说明。
