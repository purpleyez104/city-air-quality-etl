# 一天版实施计划

## 目标

在普通开发流程中完成一个可运行、可复现、可讲解的多城市空气质量 ETL 辅助项目。不启用复杂 Stage Gate，不加入调度平台、实时链路或分布式计算组件。

## 实施顺序

1. **采集与 Raw**：五城市 Source Probe，保存 JSON Snapshot 和 Manifest。
2. **MySQL 存储**：创建四张项目表，导入 Raw Record。
3. **ETL 与质量**：规范化字段，检测缺失/越界，幂等写入 Clean 与质量日志。
4. **展示与验证**：生成 Dashboard，执行 Targeted Tests，更新 README 与状态。

## 最小充分验证

- Snapshot SHA-256 和 Manifest 记录数一致。
- 五城市响应均能通过相同 Contract。
- 质量规则覆盖正常、缺失、越界和稳定问题键。
- Dashboard 能由实际输入生成。
- MySQL 可写账号就绪后验证 Schema、Raw 导入、Clean Upsert 和重复执行。

## 当前剩余工作

- 使用具备项目库写权限的 MySQL 账号执行 `init / load / run / report`。
- 对同一批输入执行两次，核对 `air_quality` 业务键数量与质量问题键集合不变。
- 基于数据库结果保存最终脱敏验收摘要。

## 非目标

Airflow、Kafka、Flink、Spark、Hive、Web Application、Docker/Kubernetes、CI/CD、预测模型、自动异常修复和生产监控均不属于本项目。
