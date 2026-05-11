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

做 Codex / agent 协作、任务拆分、问题诊断、窗口交接相关任务前，先读取：
- CONTEXT.md
- docs/agents/xhs-agent-rules.md
- docs/agents/xhs-task-template.md
- docs/agents/xhs-handoff-template.md

## Agent Skills 使用规则

本仓库维护项目专用 skills，位于：

```text
.agents/skills/
```

当前启用的项目专用 skills：

- `xhs-task-slice`：当用户给出较大的开发目标、下一阶段规划、继续任务、拆 Task、准备给 Codex 的 prompt 时使用。
- `xhs-diagnose`：当 pytest、local replay、provider、YingdaoService、KuaJingVSOpenAPI、evidence JSON、normalized_records 等出现失败时使用。
- `xhs-handoff`：当需要新窗口交接、更新进度、总结当前任务、生成下一窗口启动提示时使用。

使用原则：

1. 先使用专用 `xhs-*` skills，再考虑通用工程习惯。
2. 每次只处理一个小任务，不做大范围重构。
3. 优先读取 `CONTEXT.md` 中的共享术语，避免重复解释项目背景。
4. 结束时按固定格式输出：修改文件、测试命令、测试结果、风险/未完成项、是否需要人工 review。

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
