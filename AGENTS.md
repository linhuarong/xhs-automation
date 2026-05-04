# AGENTS.md

## 项目定位

这是一个跨平台电商自动化项目，当前重点是小红书自动化发布与热点追踪。

核心组件：
- Feishu 多维表：人工审核、任务状态、内容池、关键词池、热点池
- n8n：工作流编排
- browser-worker：RPA 调度器与 evidence 数据承接器
- 跨境卫士：账号/店铺浏览器环境启动器
- 影刀 RPA：小红书页面 UI Flow 执行器
- Selenium / Playwright：仅保留为本地 debug 或后续辅助验证
- PostgreSQL：结构化数据存储
- MinIO：截图、图片、证据文件存储
- GitHub / Codex：代码管理与 AI 开发协作

## 开发前必须读取

做小红书热点追踪相关任务前，先读取：
- docs/00_项目总览.md
- docs/02_小红书热点追踪工作流.md
- docs/03_飞书多维表设计.md
- docs/04_PostgreSQL数据库设计.md
- docs/05_MinIO截图留证规范.md
- docs/06_browser-worker开发规范.md
- docs/07_n8n工作流规范.md

做小红书发布自动化相关任务前，先读取：
- docs/00_项目总览.md
- docs/01_小红书发布工作流.md
- docs/03_飞书多维表设计.md
- docs/05_MinIO截图留证规范.md
- docs/06_browser-worker开发规范.md
- docs/07_n8n工作流规范.md

## 禁止事项

- 不允许调用小红书未授权接口。
- 不允许逆向接口请求。
- 不允许绕过浏览器模拟流程。
- 不允许把账号、密码、Cookie、Token 写入代码。
- 不允许把密钥提交到 Git。
- 不允许修改数据库结构但不生成 migration。
- 不允许跳过截图留证。
- 不允许只写代码不写日志。
- 不允许大范围重构，除非用户明确要求。
- 小红书搜索/发布主链路应走跨境卫士 + 影刀 RPA；selenium_chrome 和 direct search URL 只能作为本地 debug。

## 开发要求

- 所有任务必须有 job_id。
- 所有执行结果必须写入 PostgreSQL。
- 所有截图、页面证据、异常证据必须写入 MinIO。
- 所有人工审核状态必须回写 Feishu。
- browser-worker 必须支持可追踪日志。
- n8n 工作流必须保留输入、输出、异常分支。
- 修改代码后必须运行对应测试。
- 如果任务不明确，先给实施计划，不要直接乱写代码。

## 推荐工作方式

1. 先阅读本文件和相关 docs。
2. 先输出开发计划。
3. 再小步实现。
4. 每次只改一个功能模块。
5. 改完后说明修改了哪些文件。
6. 必须说明如何测试。
