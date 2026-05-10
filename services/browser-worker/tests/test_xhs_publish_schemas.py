from app.schemas import XhsBatchPublishRequest, XhsPublishAsset, XhsPublishJob


def test_xhs_publish_schema_defaults() -> None:
    asset = XhsPublishAsset(local_path="image.png")
    job = XhsPublishJob(
        job_id="publish-1",
        account_id="xhs_dev_01",
        provider_type="kuaijingvs_local_file_trigger_publish",
        title="标题",
        body="正文",
    )

    assert asset.asset_type == "image"
    assert job.task_type == "xhs_publish_note"
    assert job.tags == []
    assert job.assets == []


def test_xhs_batch_publish_request_defaults() -> None:
    job = XhsPublishJob(
        job_id="publish-1",
        account_id="xhs_dev_01",
        provider_type="kuaijingvs_local_file_trigger_publish",
        title="标题",
        body="正文",
    )

    request = XhsBatchPublishRequest(
        batch_id="batch-1",
        account_id="xhs_dev_01",
        provider_type="kuaijingvs_local_file_trigger_publish",
        jobs=[job],
    )

    assert request.mode == "sync"
