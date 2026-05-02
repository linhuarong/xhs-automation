# 05_MinIO截图留证规范

## 目标

统一保存自动化执行过程中产生的截图、页面证据、异常证据、素材文件。

## 推荐路径

xhs/
  search/
    yyyy/mm/dd/{job_id}/
      search_page.png
      result_001_detail.png
      result_002_detail.png

  publish/
    yyyy/mm/dd/{job_id}/
      before_publish.png
      upload_done.png
      publish_result.png
      error.png

## 规则

- 所有截图必须绑定 job_id。
- 数据库保存 MinIO object key。
- Feishu 可保存附件或外链。
- 异常必须保存 error.png 和 error.json。
