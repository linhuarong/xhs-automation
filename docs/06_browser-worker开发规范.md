# 06_browser-worker开发规范

## 定位

browser-worker 在 V2 架构中定位为：RPA 调度器 + evidence 数据承接器。

它不再作为小红书主链路的直接页面操作者。主链路应由 browser-worker 接收 job、选择 provider、调度跨境卫士环境和影刀 RPA 应用，再读取影刀输出的 evidence JSON。

## 第一阶段能力

- 接收 `search_job`
- 接收 `publish_job`
- 校验 job schema
- 记录 job 状态和结构化日志
- 选择 provider
- 调用影刀 RPA 服务
- 读取 evidence JSON
- 返回 WorkerResult
- 后续写入 PostgreSQL
- 后续回写 Feishu

## Provider 规则

### `selenium_chrome`

- 仅用于本地 debug。
- 可用于验证 FastAPI、截图、selector、evidence JSON、normalized_records。
- direct search URL 只允许 debug。
- 不作为小红书搜索/发布的主链路。

### `yingdao_rpa`

- browser-worker 调用影刀 API 或本地影刀运行入口。
- 影刀负责执行小红书页面 UI Flow。
- 影刀输出 evidence JSON。

### `kuaijingvs_yingdao_rpa`

- 后续主链路。
- browser-worker 先通过 KuaJingVSOpenAPI 启动账号/店铺环境。
- 再调用 YingdaoService 执行影刀应用。
- browser-worker 读取影刀输出 evidence JSON 并返回 WorkerResult。

## search_job 执行规范

1. browser-worker 接收 `SearchJob`。
2. 根据 `provider_type` 选择 provider。
3. `provider_type=yingdao_rpa` 或 `kuaijingvs_yingdao_rpa` 时，browser-worker 调用影刀应用。
4. 影刀执行搜索 UI Flow。
5. 影刀输出 `search_evidence.json`。
6. browser-worker 读取 evidence JSON。
7. browser-worker 返回 WorkerResult。
8. 后续写入 PostgreSQL 并回写 Feishu 热点池。

## publish_job 执行规范

1. browser-worker 接收 `PublishJob`。
2. 根据 `provider_type` 选择 provider。
3. 主链路调用影刀发布应用。
4. 影刀在跨境卫士环境中执行上传、填写、提交前确认等 UI Flow。
5. 影刀输出 `publish_evidence.json`。
6. browser-worker 读取结果、截图和 evidence。
7. 遇到验证、风控或异常时返回 `waiting_human_verification` 或 `failed`。

## evidence 数据承接

browser-worker 必须把影刀输出转换为统一 WorkerResult：

- `job_id`
- `status`
- `message`
- `error_code`
- `error_message`
- `screenshot_url`
- `evidence_json_path`
- `items`
- `normalized_records`

搜索任务中，`normalized_records` 是 PostgreSQL、飞书热点池、Coze/Dify 的统一数据接口。

## 日志要求

- 每个 job 必须有 `job_id`。
- 每个关键步骤必须写结构化日志。
- 调用 provider、启动 RPA、查询 RPA 状态、读取 evidence、写 PostgreSQL 都应记录 step。
- 失败和人工处理状态必须带 `error_code`。

## 禁止事项

- 不调用小红书未授权接口。
- 不逆向 request。
- 不伪造 XHR、fetch、token、cookie、sign。
- 不绕过登录、验证码、扫码、安全确认、风控或账号限制。
- 不实现验证码自动处理。
- 不隐藏自动化特征或规避平台检测。
- 不把账号、密码、Cookie、Token、密钥写入代码。
