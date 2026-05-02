# 06_browser-worker开发规范

## 定位

browser-worker 是浏览器自动化执行层，负责接收 n8n 或其他调度器传入的 job，并通过浏览器模拟人工操作。

## 第一阶段功能

- 接收 search_job
- 接收 publish_job
- 打开指定浏览器配置
- 执行页面操作
- 截图
- 上传 MinIO
- 写入 PostgreSQL
- 返回执行结果

## 要求

- 每个 job 必须有 job_id。
- 每个步骤必须有日志。
- 页面异常必须截图。
- 不允许硬编码账号密码。
- 浏览器 profile 与 account_id 解耦。
- 预留 Selenium / Playwright 切换空间。
