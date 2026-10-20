# 一天版实施计划

## 目标

在普通开发流程中完成一个可运行、可复现、可讲解的多城市空气质量 ETL 辅助项目。不启用复杂 Stage Gate，不加入调度平台、实时链路或分布式计算组件。

## 实施顺序

1. **采集与 Raw**：五城市 Source Probe，保存 JSON Snapshot 和 Manifest。
2. **MySQL 存储**：创建四张项目表，导入 Raw Record。
3. **ETL 与质量**：规范化字段，检测缺失/越界，幂等写入 Clean 与质量日志。
4. **展示与验证**：生成 Dashboard，执行 Targeted Tests，更新 README 与状态。
5. **历史初始化**：校验 2025 年 CSV，提取五城市，以固定小时规则写入 Raw/Clean 并验证幂等。
6. **API 增量衔接**：显式来源优先级，报告新增/重叠/变化状态，并对真实五城市批次重复验收。
7. **全年展示**：使用历史与 API Clean 数据生成来源分段 Dashboard、月度汇总和可对账报告，并执行 Browser 视觉验收。

## 最小充分验证

- Snapshot SHA-256 和 Manifest 记录数一致。
- 五城市响应均能通过相同 Contract。
- 质量规则覆盖正常、缺失、越界和稳定问题键。
- Dashboard 能由实际输入生成。
- MySQL 可写账号就绪后验证 Schema、Raw 导入、Clean Upsert 和重复执行。
- 历史 CSV 全量转换应验证文件数、日期范围、回退数、缺失数和稳定来源键。

## 当前状态

- API 小窗口与 2025 年历史 Raw/Clean 均已完成真实 MySQL 验收。
- 历史初始化 Stage 本身停止在 Raw/Clean；后续全年展示 Stage 只读取既有 Clean 数据，不为历史来源新增填充或额外分析层。
- API 增量与来源优先级已经通过 Fixture Integration Test 和真实五城市批次验收。
- 全年 Dashboard 与分析输出已完成；六类文件、数据对账、桌面和窄屏视觉检查均通过。
- 当前一天范围已经完成。后续如继续开发，应重新确认新 Stage，不自动增加调度或分布式组件。

## 非目标

Airflow、Kafka、Flink、Spark、Hive、Web Application、Docker/Kubernetes、CI/CD、预测模型、自动异常修复和生产监控均不属于本项目。
