"""CLI tests for async app subscriber rollout commands and live progress follower."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner
from valstorm.transport import SSEEvent

from valstorm_cli.main import app as cli_app

runner = CliRunner()


def _make_fake_sdk(final_status: str = "completed"):
    job_id = "djob_cli00000000001"
    failed_orgs = (
        [
            {
                "organization_id": "org_bad",
                "organization_name": "Legacy Corp",
                "error_code": "DDL_CONSTRAINT_ERROR",
                "error_message": "FK mismatch",
            }
        ]
        if final_status == "completed_with_errors"
        else []
    )
    final_report = {
        "job_id": job_id,
        "app_id": "app_base",
        "app_name": "Base",
        "app_version": "2.4.0",
        "status": final_status,
        "total_duration_ms": 4200,
        "counts": {
            "total_orgs": 2,
            "completed_orgs": 2,
            "succeeded": 2 if final_status == "completed" else 1,
            "failed": 0 if final_status == "completed" else 1,
            "skipped": 0,
            "in_progress": 0,
            "pending": 0,
        },
        "totals": {
            "schemas_in_bundle": 52,
            "records_in_bundle": 31,
            "total_schemas_applied": 104,
            "total_records_applied": 62,
        },
        "org_results": [],
        "failed_orgs": failed_orgs,
        "retry": {
            "available": bool(failed_orgs),
            "api_endpoint": f"/v1/apps/deployments/{job_id}/retry-failed",
            "cli_command": f"valstorm app deploy-retry {job_id}",
        },
    }

    running_snapshot = {
        **final_report,
        "status": "running",
        "counts": {
            "total_orgs": 2,
            "completed_orgs": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "in_progress": 2,
            "pending": 0,
        },
    }

    apps = MagicMock()
    apps.deploy_to_marketplace.return_value = {
        "status": "ok",
        "app_id": "app_base",
        "schemas_published": 52,
        "records_published": 31,
    }
    apps.update_subscribers.return_value = {
        "status": "accepted",
        "job_id": job_id,
        "deployment_job_id": job_id,
        "app_id": "app_base",
    }
    apps.get_deployment.side_effect = [running_snapshot, final_report]
    apps.stream_deployment.return_value = iter(
        [
            SSEEvent(
                id="1-0",
                event="org_completed",
                data={
                    "type": "org_completed",
                    "job_id": job_id,
                    "progress": {"total_orgs": 2, "completed_orgs": 1},
                    "data": {
                        "organization_id": "org_1",
                        "organization_name": "Valstorm LLC",
                        "schemas_synced": 52,
                        "records_applied": 31,
                        "duration_ms": 1500,
                    },
                },
                raw_data="{}",
            ),
            SSEEvent(
                id="2-0",
                event="job_completed",
                data={
                    "type": "job_completed",
                    "job_id": job_id,
                    "progress": final_report["counts"],
                    "data": final_report,
                },
                raw_data="{}",
            ),
        ]
    )
    apps.retry_failed_deployment.return_value = {
        "status": "accepted",
        "job_id": "djob_retry000000001",
        "deployment_job_id": "djob_retry000000001",
    }
    apps.list_deployments.return_value = [final_report]

    sdk = SimpleNamespace(apps=apps, close=MagicMock())
    fake_auth = SimpleNamespace(
        access_token="fake-token",
        sandbox=None,
        get_sdk_client=lambda: sdk,
    )
    return fake_auth, sdk, final_report


def test_publish_update_subscribers_no_wait_json():
    fake_auth, sdk, _ = _make_fake_sdk("completed")
    with patch("valstorm_cli.auth.get_auth", return_value=fake_auth):
        res = runner.invoke(
            cli_app,
            ["app", "publish", "app_base", "--update-subscribers", "--no-wait", "--json"],
        )
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["subscribers"]["deployment_job_id"] == "djob_cli00000000001"
    sdk.apps.stream_deployment.assert_not_called()


def test_publish_update_subscribers_follow_completed_exits_0():
    fake_auth, sdk, _ = _make_fake_sdk("completed")
    with patch("valstorm_cli.auth.get_auth", return_value=fake_auth):
        res = runner.invoke(
            cli_app,
            ["app", "publish", "app_base", "--update-subscribers", "--json"],
        )
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data["deployment"]["status"] == "completed"
    sdk.apps.stream_deployment.assert_called_once()


def test_publish_update_subscribers_partial_failure_exits_1_and_prints_retry_hint():
    fake_auth, _sdk, _ = _make_fake_sdk("completed_with_errors")
    with patch("valstorm_cli.auth.get_auth", return_value=fake_auth):
        res = runner.invoke(
            cli_app,
            ["app", "publish", "app_base", "--update-subscribers"],
        )
    assert res.exit_code == 1
    assert "Legacy Corp" in res.output
    assert "valstorm app deploy-retry djob_cli00000000001" in res.output


def test_deploy_status_follow_and_retry_no_wait():
    fake_auth, _sdk, _ = _make_fake_sdk("completed")
    with patch("valstorm_cli.auth.get_auth", return_value=fake_auth):
        res = runner.invoke(cli_app, ["app", "deploy-status", "djob_cli00000000001", "--follow"])
    assert res.exit_code == 0, res.output
    assert "COMPLETED" in res.output

    with patch("valstorm_cli.auth.get_auth", return_value=fake_auth):
        res_retry = runner.invoke(cli_app, ["app", "deploy-retry", "djob_cli00000000001", "--no-wait", "--json"])
    assert res_retry.exit_code == 0, res_retry.output
    assert json.loads(res_retry.output)["job_id"] == "djob_retry000000001"
