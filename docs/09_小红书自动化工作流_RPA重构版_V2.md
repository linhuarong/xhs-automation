# 09_小红书自动化工作流_RPA重构版_V2

## 1. 重构背景

早期 browser-worker 原型直接通过 `selenium_chrome_provider` 打开小红书页面，完成搜索、输入、截图、DOM 提取和 evidence JSON 生成。该方式适合本地验证选择器和数据结构，但不适合作为账号环境、店铺环境和长期运营的主链路。

V2 重构后，主链路改为：

- 跨境卫士负责账号/店铺浏览器环境启动。
- 影刀 RPA 负责小红书页面 UI Flow 执行。
- browser-worker 负责接收 job、选择 provider、调度 RPA、读取 evidence JSON、返回 WorkerResult。
- PostgreSQL、飞书热点池、Coze/Dify 继续消费 `normalized_records`。
- `selenium_chrome_provider` 只保留为本地 debug。
- direct search URL 只允许 debug，不作为生产主链路。

## 2. 新旧架构对比

旧架构：

```text
browser-worker
-> SeleniumChromeProvider
-> 直接打开小红书页面
-> 输入关键词或发布内容
-> 截图和 DOM 提取
-> evidence JSON
```

新架构：

```text
browser-worker
-> Provider Router
-> KuaJingVS / 跨境卫士启动账号环境
-> Yingdao / 影刀 RPA 执行小红书 UI Flow
-> 影刀输出 evidence JSON
-> browser-worker 读取 evidence JSON
-> PostgreSQL / 飞书热点池 / Coze
```

## 3. 新总体架构图

```text
Feishu 多维表
-> n8n 定时或人工触发
-> browser-worker 接收 search_job / publish_job
-> Provider Router 选择 provider_type
-> KuaJingVSOpenAPI 启动账号/店铺环境
-> YingdaoService 启动影刀应用并等待执行完成
-> 影刀 RPA 在真实浏览器环境中执行 UI Flow
-> 影刀输出截图、页面证据、search_evidence.json / publish_evidence.json
-> browser-worker 读取 evidence JSON
-> WorkerResult 返回 evidence_json_path、items、normalized_records、状态
-> PostgreSQL 写入结构化记录
-> Feishu 热点池 / 发布池回写
-> Coze / Dify 做热点分析或内容生成
-> OpenClaw 通知人工处理异常
```

## 4. 组件职责

### Feishu

- 运营入口和人工审核界面。
- 维护关键词池、热点池、发布池、人工处理状态。
- 展示从 PostgreSQL / n8n 回写的结果摘要、截图链接和异常原因。

### n8n

- 定时读取 Feishu 关键词池或发布池。
- 生成标准 `search_job` / `publish_job`。
- 调用 browser-worker API。
- 接收 WorkerResult，处理成功、失败、人工处理分支。
- 回写 Feishu，不直接操作浏览器页面。

### browser-worker

- 定位从“浏览器页面执行器”调整为“RPA 调度器 + evidence 数据承接器”。
- 接收 job，校验 schema，记录 job 状态。
- 根据 `provider_type` 选择 provider。
- 调用 KuaJingVSOpenAPI 启动环境。
- 调用 YingdaoService 启动影刀应用、轮询状态、等待完成。
- 读取影刀输出的 evidence JSON。
- 返回 WorkerResult。
- 后续写入 PostgreSQL，并触发 n8n/Feishu/Coze 下游承接。

### KuaJingVS / 跨境卫士

- 作为账号/店铺环境启动器。
- 负责 account_id 到浏览器环境/profile_id 的映射。
- 提供环境启动、停止、状态查询能力。
- 不负责小红书页面动作。

### Yingdao / 影刀 RPA

- 作为小红书 UI Flow 执行器。
- 在跨境卫士启动的真实浏览器环境中执行搜索、发布等页面流程。
- 遇到登录、验证码、扫码、安全确认、风控或账号限制时暂停并输出人工处理状态。
- 输出截图、异常证据和 evidence JSON。
- 不调用小红书未授权接口，不逆向 request，不伪造 XHR/fetch。

### PostgreSQL

- 保存 search evidence 头信息和 normalized search records。
- 后续保存 publish evidence、执行日志、Feishu 映射关系。
- 消费 browser-worker 读取到的 evidence JSON，不依赖 Selenium DOM 提取。

### MinIO

- 后续承接截图、图片素材、页面证据、error.json。
- 数据库只保存 object key 或 URL。
- V2 文档阶段只定义承接方式，不接真实 MinIO。

### Coze / Dify

- 消费 `normalized_records` 进行热点总结、趋势判断、内容角度推荐。
- 不直接控制浏览器，不直接修改业务状态。

### OpenClaw

- 承接人工协作通知。
- 通知 waiting_human_verification、failed、success。
- 支持后续人工重试、继续、取消入口。

## 5. search_job 新链路

```text
Feishu 关键词池
-> n8n 生成 search_job
-> browser-worker 接收 POST /api/xhs/search
-> Provider Router 选择 kuaijingvs_yingdao_rpa
-> KuaJingVSOpenAPI 启动 account_id 对应环境
-> YingdaoService 启动“小红书搜索 RPA 应用”
-> 影刀在页面执行搜索 UI Flow
-> 影刀截图并提取前 N 条可见结果
-> 影刀输出 search_evidence.json
-> browser-worker 读取 evidence
-> 返回 WorkerResult
-> PostgreSQL 写入 normalized_records
-> n8n 回写 Feishu 热点池
-> Coze/Dify 可选做热点分析
```

## 6. publish_job 新链路

```text
Feishu 发布池
-> n8n 生成 publish_job
-> browser-worker 接收 POST /api/xhs/publish
-> Provider Router 选择 kuaijingvs_yingdao_rpa
-> KuaJingVSOpenAPI 启动 account_id 对应环境
-> YingdaoService 启动“小红书发布 RPA 应用”
-> 影刀在页面执行上传、填写、提交前确认等 UI Flow
-> 遇到登录/验证码/风控则返回 waiting_human_verification
-> 影刀输出 publish_evidence.json
-> browser-worker 读取 evidence
-> 返回 WorkerResult
-> PostgreSQL / Feishu 承接发布状态
```

## 7. evidence JSON 标准

搜索 evidence 需要至少包含：

```json
{
  "job_id": "search-001",
  "task_type": "xhs_keyword_search",
  "status": "success",
  "keyword": "眼影",
  "account_id": "xhs_dev_01",
  "provider_type": "kuaijingvs_yingdao_rpa",
  "captured_at": "2026-05-05T00:00:00Z",
  "screenshot_path": "xhs/search/2026/05/05/search-001/search_success.png",
  "item_count": 5,
  "normalized_record_count": 5,
  "result_area_found": true,
  "items": [],
  "normalized_records": []
}
```

发布 evidence 需要至少包含：

```json
{
  "job_id": "publish-001",
  "task_type": "xhs_publish",
  "status": "success",
  "account_id": "xhs_dev_01",
  "provider_type": "kuaijingvs_yingdao_rpa",
  "captured_at": "2026-05-05T00:00:00Z",
  "note_url": "https://www.xiaohongshu.com/explore/...",
  "screenshots": [],
  "error_code": null,
  "error_message": null
}
```

## 8. normalized_records 标准

`normalized_records` 是后续 PostgreSQL、飞书热点池、Coze/Dify 的统一数据接口。每条搜索结果建议包含：

```json
{
  "job_id": "search-001",
  "keyword": "眼影",
  "account_id": "xhs_dev_01",
  "provider_type": "kuaijingvs_yingdao_rpa",
  "captured_at": "2026-05-05T00:00:00Z",
  "rank": 1,
  "title": "示例标题",
  "author": "作者",
  "published_at_text": "05-05",
  "note_id": "note-id",
  "note_url": "https://www.xiaohongshu.com/explore/note-id",
  "metric_raw_text": "1.2万",
  "like_count_text": "1.2万",
  "screenshot_path": "xhs/search/2026/05/05/search-001/search_success.png",
  "evidence_json_path": "xhs/search/2026/05/05/search-001/search_evidence.json"
}
```

## 9. 影刀应用入参

搜索应用入参建议：

- `job_id`
- `account_id`
- `keyword`
- `limit`
- `capture_screenshot`
- `evidence_output_dir`
- `run_mode`：`manual_low_frequency` 或后续扩展模式

发布应用入参建议：

- `job_id`
- `account_id`
- `title`
- `body`
- `tags`
- `image_paths` 或素材引用
- `publish_mode`
- `scheduled_at`
- `evidence_output_dir`

## 10. 影刀应用出参

通用出参：

- `job_id`
- `status`：`success` / `failed` / `waiting_human_verification`
- `message`
- `error_code`
- `error_message`
- `evidence_json_path`
- `screenshot_path`
- `items`
- `normalized_records`

## 11. browser-worker Provider Router 设计

Provider Router 根据 `provider_type` 选择执行路径：

- `selenium_chrome`：仅本地 debug，允许验证 URL、截图、selector、evidence 格式。
- `yingdao_rpa`：调用本机或固定环境中的影刀应用。
- `kuaijingvs_yingdao_rpa`：先通过跨境卫士启动账号环境，再调用影刀应用，是后续主链路。

Router 不写页面选择器，不写小红书页面动作，不调用小红书未授权接口。

## 12. YingdaoService 设计

YingdaoService 后续负责：

- 读取影刀 token 或本地配置。
- 启动指定影刀应用。
- 传入 search_job / publish_job。
- 查询 run 状态。
- 等待完成或超时。
- 读取应用输出。
- 将影刀状态映射为 WorkerResult。

YingdaoService 不处理验证码，不隐藏自动化特征，不伪造任何平台请求。

## 13. KuaJingVSOpenAPI 环境启动器设计

KuaJingVSOpenAPI 后续负责：

- 根据 `account_id` 查找跨境卫士 profile。
- 启动浏览器环境。
- 返回环境 ID、窗口信息或影刀可绑定的上下文信息。
- 查询环境状态。
- 关闭或释放环境。

它只负责环境生命周期，不负责小红书页面 UI 操作。

## 14. PostgreSQL 后续接入方式

PostgreSQL 继续消费 evidence JSON：

- `xhs_search_evidence` 保存一次搜索 evidence 头信息。
- `xhs_search_records` 保存每条 normalized record。
- 后续扩展 publish evidence、execution logs、asset files。

写入逻辑应以 `evidence_json_path` 和 `normalized_records` 为主，不直接依赖 Selenium 的 DOM 提取过程。

## 15. 飞书热点池回写方式

n8n 或后续回写服务从 PostgreSQL / WorkerResult 中读取：

- `job_id`
- `keyword`
- `rank`
- `title`
- `author`
- `note_url`
- `metric_raw_text`
- `like_count_text`
- `screenshot_path`
- `evidence_json_path`
- `status`
- `error_message`

Feishu 只做运营展示和人工审核，不作为完整 evidence 存储。

## 16. 后续 Task 开发顺序

- Task 24A：定义 Provider Router、provider_type 路由表和 debug-only 兼容策略。
- Task 24B：实现 YingdaoService skeleton，只做 token/config/start/query/wait 的接口骨架和 mock 测试。
- Task 24C：实现 KuaJingVSOpenAPI skeleton，只做环境启动器接口骨架和 mock 测试。
- Task 24D：把 `/api/xhs/search` 从 direct Selenium 主路径切到 provider router，保留 `selenium_chrome` 为 debug-only。

## 17. 强制禁止

- 不调用小红书未授权接口。
- 不逆向 request。
- 不伪造 XHR、fetch、token、cookie、sign。
- 不绕过登录、验证码、扫码、安全确认、风控或账号限制。
- 不实现隐藏自动化特征、规避检测或验证码自动处理。
- 不把账号、密码、Cookie、Token、密钥写入代码。
