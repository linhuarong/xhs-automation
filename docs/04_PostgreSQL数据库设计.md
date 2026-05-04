# 04_PostgreSQL数据库设计

## 核心表

建议第一阶段包含：

- xhs_search_evidence
- xhs_search_records
- xhs_search_jobs
- xhs_search_results
- xhs_note_details
- xhs_publish_jobs
- xhs_publish_results
- asset_files
- execution_logs

## 设计原则

- Feishu 负责人工审核和运营展示。
- PostgreSQL 负责结构化历史数据。
- MinIO 负责截图、图片、证据文件。
- 数据库只保存 MinIO 路径，不直接保存大文件。
- V2 主链路中，PostgreSQL 优先消费影刀 RPA 输出的 evidence JSON 和 browser-worker 读取后的 normalized_records。
- PostgreSQL 不依赖 Selenium DOM 提取作为主输入。
