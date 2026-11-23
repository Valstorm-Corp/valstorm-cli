"""Unit tests for the slimmed Open Valstorm CLI (FI-598)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
from typer.testing import CliRunner

from valstorm_cli.auth import ENVIRONMENTS, ValstormAuth, get_api_base_url, normalize_api_url
from valstorm_cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# 1. Command Surface & Removals
# ---------------------------------------------------------------------------

def test_root_command_surface_slimmed():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0

    # Removed legacy / non-core commands must NOT appear
    for removed in ("hermes", "scaffold", "agent", "mcp", "deploy", "manifest", "project"):
        assert f"  {removed} " not in result.output

    # Core Open Valstorm commands MUST appear
    for core in ("init", "open", "auth", "schema", "record", "fn", "app", "sandbox", "vfs", "rpc", "pull", "push", "sql", "graphql", "search", "ask"):
        assert core in result.output

    # Stubs directory and project.py must be removed
    pkg_dir = Path(__file__).resolve().parents[1] / "src" / "valstorm_cli"
    assert not (pkg_dir / "stubs").exists()
    assert not (pkg_dir / "project.py").exists()


def test_vfs_command_surface_slimmed():
    from valstorm_cli.vfs_cmds import vfs_app

    registered_names = {cmd.name for cmd in vfs_app.registered_commands}
    assert registered_names == {"ls", "info", "upload", "download", "mv", "rm", "index"}


def test_sandbox_command_surface_slimmed():
    result = runner.invoke(app, ["sandbox", "--help"])
    assert result.exit_code == 0
    for expected in ("list", "create", "refresh", "delete", "use", "users"):
        assert expected in result.output
    for removed in ("use-parent", "switch-back"):
        assert removed not in result.output


# ---------------------------------------------------------------------------
# 2. Custom / Self-Hosted Open Valstorm URL & Token Support
# ---------------------------------------------------------------------------

def test_environments_exclude_blue_green():
    assert set(ENVIRONMENTS.keys()) == {"prod", "dev", "local"}


def test_normalize_api_url():
    assert normalize_api_url("https://api.acme.internal") == "https://api.acme.internal/v1"
    assert normalize_api_url("https://api.acme.internal/") == "https://api.acme.internal/v1"
    assert normalize_api_url("https://api.acme.internal/v1") == "https://api.acme.internal/v1"
    assert normalize_api_url("https://api.acme.internal/v1/") == "https://api.acme.internal/v1"


def test_self_hosted_env_var_and_headless_token(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("VALSTORM_API_URL", "https://open.acme.internal")
    monkeypatch.setenv("VALSTORM_TOKEN", "pat_headless_123")

    assert get_api_base_url("prod") == "https://open.acme.internal/v1"

    auth = ValstormAuth(profile="ci", env="prod")
    assert auth.api_base_url == "https://open.acme.internal/v1"
    assert auth.access_token == "pat_headless_123"


def test_saved_custom_api_url_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("VALSTORM_API_URL", raising=False)
    monkeypatch.delenv("VALSTORM_BASE_URL", raising=False)

    auth = ValstormAuth(profile="selfhosted", env="custom", api_url="https://api.myorg.dev/v1")
    auth.save_tokens(access_token="tok_123", api_url="https://api.myorg.dev/v1", web_url="https://app.myorg.dev")

    reloaded = ValstormAuth(profile="selfhosted", env="custom")
    assert reloaded.api_base_url == "https://api.myorg.dev/v1"
    assert reloaded.web_base_url == "https://app.myorg.dev"


# ---------------------------------------------------------------------------
# 3. Query (sql / graphql) & record get — Default NO HYDRATE
# ---------------------------------------------------------------------------

def _patch_auth_with_sdk(monkeypatch, sdk_mock=None, client_mock=None):
    fake_auth = MagicMock()
    fake_auth.sandbox = None
    fake_auth.access_token = "tok_test"
    fake_auth.api_base_url = "https://api.valstorm.com/v1"
    fake_auth.get_sdk_client.return_value = sdk_mock or MagicMock()
    fake_auth.get_client.return_value = client_mock or MagicMock()
    monkeypatch.setattr("valstorm_cli.auth.get_auth", lambda **kwargs: fake_auth)
    return fake_auth


def test_sql_defaults_to_no_hydrate(monkeypatch):
    sdk = MagicMock()
    sdk.query.sql.return_value = [{"id": "con_1", "owner": "user_1"}]
    _patch_auth_with_sdk(monkeypatch, sdk_mock=sdk)

    result = runner.invoke(app, ["sql", "SELECT id, owner FROM contact LIMIT 1"])
    assert result.exit_code == 0, result.output
    sdk.query.sql.assert_called_once_with(
        "SELECT id, owner FROM contact LIMIT 1",
        limit=None,
        hydrate=False,
        bypass_cache=False,
    )
    parsed = json.loads(result.output)
    assert parsed[0]["owner"] == "user_1"


def test_sql_with_hydrate_flag(monkeypatch):
    sdk = MagicMock()
    sdk.query.sql.return_value = [{"id": "con_1", "owner": {"id": "user_1", "name": "Jared"}}]
    _patch_auth_with_sdk(monkeypatch, sdk_mock=sdk)

    result = runner.invoke(app, ["sql", "SELECT id, owner FROM contact LIMIT 1", "--hydrate"])
    assert result.exit_code == 0, result.output
    sdk.query.sql.assert_called_once_with(
        "SELECT id, owner FROM contact LIMIT 1",
        limit=None,
        hydrate=True,
        bypass_cache=False,
    )
    parsed = json.loads(result.output)
    assert parsed[0]["owner"] == {"id": "user_1", "name": "Jared"}


def test_graphql_defaults_to_no_hydrate_and_preserves_top_level_and_joins(monkeypatch):
    raw_gql = {
        "data": {
            "contact": [
                {
                    "id": "con_1",
                    "name": "Alice",
                    "owner": {"id": "user_1", "name": "Jared"},
                    "tags": [{"id": "tag_1", "name": "VIP"}],
                    "company": {"id": "acc_1", "name": "Acme", "domain": "acme.com"},
                }
            ]
        }
    }
    sdk = MagicMock()
    sdk.query.graphql.return_value = raw_gql
    _patch_auth_with_sdk(monkeypatch, sdk_mock=sdk)

    # Default (no --hydrate): nested {id, name} lookups unpacked to raw IDs
    res_default = runner.invoke(app, ["graphql", "{ contact { id name owner { id name } } }"])
    assert res_default.exit_code == 0, res_default.output
    parsed_default = json.loads(res_default.output)
    rec = parsed_default["data"]["contact"][0]
    assert rec["id"] == "con_1"
    assert rec["name"] == "Alice"
    assert rec["owner"] == "user_1"
    assert rec["tags"] == ["tag_1"]
    assert rec["company"] == {"id": "acc_1", "name": "Acme", "domain": "acme.com"}

    # Explicit --hydrate: preserves {id, name}
    res_hydrated = runner.invoke(app, ["graphql", "{ contact { id name owner { id name } } }", "--hydrate"])
    assert res_hydrated.exit_code == 0, res_hydrated.output
    parsed_hydrated = json.loads(res_hydrated.output)
    assert parsed_hydrated["data"]["contact"][0]["owner"] == {"id": "user_1", "name": "Jared"}
    assert parsed_hydrated["data"]["contact"][0]["tags"] == [{"id": "tag_1", "name": "VIP"}]


def test_record_get_defaults_to_no_hydrate(monkeypatch):
    client = MagicMock()
    client.get.return_value = httpx.Response(200, json={"id": "con_1", "owner": "user_1"})
    _patch_auth_with_sdk(monkeypatch, client_mock=client)

    res = runner.invoke(app, ["record", "get", "contact", "con_1"])
    assert res.exit_code == 0, res.output
    client.get.assert_called_once_with("/object/contact/con_1", params={"hydrate": "false"})

    client.reset_mock()
    client.get.return_value = httpx.Response(200, json={"id": "con_1", "owner": {"id": "user_1", "name": "Jared"}})
    res_h = runner.invoke(app, ["record", "get", "contact", "con_1", "--hydrate"])
    assert res_h.exit_code == 0, res_h.output
    client.get.assert_called_once_with("/object/contact/con_1", params={"hydrate": "true"})


# ---------------------------------------------------------------------------
# 4. PostgreSQL Schema Reflection (`schema status`, `schema sync`)
# ---------------------------------------------------------------------------

def test_schema_status_and_sync(monkeypatch):
    client = MagicMock()
    client.get.return_value = httpx.Response(
        200,
        json={
            "is_in_sync": False,
            "unregistered_tables": ["custom_ledger"],
            "missing_tables": [],
            "table_drift": {"contact": {"unregistered_columns": ["external_ref"], "deleted_columns": []}},
        },
    )
    client.post.return_value = httpx.Response(
        200,
        json={"created_schemas": ["custom_ledger"], "updated_schemas": []},
    )
    _patch_auth_with_sdk(monkeypatch, client_mock=client)

    res_status = runner.invoke(app, ["schema", "status"])
    assert res_status.exit_code == 0, res_status.output
    assert "custom_ledger" in res_status.output
    client.get.assert_called_once_with("/schema/sync/status", timeout=30.0)

    res_sync = runner.invoke(app, ["schema", "sync", "-o", "custom_ledger", "--prune"])
    assert res_sync.exit_code == 0, res_sync.output
    assert "custom_ledger" in res_sync.output
    client.post.assert_called_once_with(
        "/schema/sync",
        json={"objects": ["custom_ledger"], "prune_missing_columns": True},
        timeout=60.0,
    )


# ---------------------------------------------------------------------------
# 5. Serverless Functions (`fn validate`, `fn run`)
# ---------------------------------------------------------------------------

def test_fn_validate_and_run(tmp_path, monkeypatch):
    fn_file = tmp_path / "greet.py"
    fn_file.write_text("async def handler(inputs, platform):\n    return {'ok': True}\n")

    client = MagicMock()
    client.post.side_effect = [
        httpx.Response(200, json={"valid": True, "result": {"ok": True}}),
        httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"}),
        httpx.Response(200, json={"ok": True}, headers={"content-type": "application/json"}),
    ]
    _patch_auth_with_sdk(monkeypatch, client_mock=client)

    res_val = runner.invoke(app, ["fn", "validate", str(fn_file)])
    assert res_val.exit_code == 0, res_val.output
    assert client.post.call_args_list[0].args[0] == "/function/validate"

    res_run_file = runner.invoke(app, ["fn", "run", str(fn_file), "-i", '{"name": "world"}'])
    assert res_run_file.exit_code == 0, res_run_file.output
    call_payload = client.post.call_args_list[1].kwargs["json"]
    assert "code" in call_payload
    assert call_payload["inputs"] == {"name": "world"}

    res_run_id = runner.invoke(app, ["fn", "run", "func_abc123"])
    assert res_run_id.exit_code == 0, res_run_id.output
    assert client.post.call_args_list[2].kwargs["json"]["function_id"] == "func_abc123"


# ---------------------------------------------------------------------------
# 6. Universal Platform RPC (`rpc list`, `rpc call`)
# ---------------------------------------------------------------------------

def test_rpc_list_and_call(monkeypatch):
    client = MagicMock()
    client.get.return_value = httpx.Response(
        200,
        json={"methods": [{"target": "utils.ping", "scope": "read:utils", "description": "Health ping"}]},
    )
    client.post.return_value = httpx.Response(
        200,
        json={"status": "ok", "target": "utils.ping", "result": {"pong": True, "count": 3}},
    )
    _patch_auth_with_sdk(monkeypatch, client_mock=client)

    res_list = runner.invoke(app, ["rpc", "list", "-n", "utils", "-q", "ping"])
    assert res_list.exit_code == 0, res_list.output
    assert "utils.ping" in res_list.output
    client.get.assert_called_once_with("/platform/methods", params={"namespace": "utils", "q": "ping"}, timeout=30.0)

    res_call = runner.invoke(app, ["rpc", "call", "utils.ping", "-a", "count=3", "-a", "active=true", "-a", "msg=hi"])
    assert res_call.exit_code == 0, res_call.output
    assert json.loads(res_call.output) == {"pong": True, "count": 3}
    client.post.assert_called_once_with(
        "/platform/invoke/utils.ping",
        json={"count": 3, "active": True, "msg": "hi"},
        timeout=60.0,
    )


# ---------------------------------------------------------------------------
# 7. Single-Roundtrip ACID `pull` & `push`
# ---------------------------------------------------------------------------

def test_single_roundtrip_pull_and_push(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "valstorm.json").write_text(json.dumps({"name": "demo", "env": "prod", "profile": "default"}))

    sdk = MagicMock()
    sdk.apps.pull_metadata.return_value = {
        "schemas": {"contact": {"api_name": "contact", "title": "Contact", "properties": {}}},
        "objects": {
            "function": [{"id": "func_1", "name": "hello", "file_name": "hello.py", "code": "def run():\n    return 1\n"}]
        },
    }
    sdk.apps.push_metadata.return_value = {
        "schemas_pushed": 1,
        "created_count": 0,
        "updated_count": 1,
        "objects": {"function": [{"id": "func_1", "name": "hello", "file_name": "hello.py"}]},
    }
    _patch_auth_with_sdk(monkeypatch, sdk_mock=sdk)

    res_pull = runner.invoke(app, ["pull", "--force"])
    assert res_pull.exit_code == 0, res_pull.output
    assert (tmp_path / "schemas" / "contact.json").exists()
    assert (tmp_path / "function" / "hello.py").read_text() == "def run():\n    return 1\n"
    assert (tmp_path / ".valstorm" / "metadata.json").exists()

    # Dry-run push must NOT call push_metadata
    res_dry = runner.invoke(app, ["push", "--dry-run"])
    assert res_dry.exit_code == 0, res_dry.output
    sdk.apps.push_metadata.assert_not_called()

    # Real push calls single-roundtrip push_metadata once
    res_push = runner.invoke(app, ["push"])
    assert res_push.exit_code == 0, res_push.output
    sdk.apps.push_metadata.assert_called_once()
    sent_payload = sdk.apps.push_metadata.call_args.args[0]
    assert len(sent_payload["schemas"]) == 1
    assert sent_payload["objects"]["function"][0]["id"] == "func_1"


# ---------------------------------------------------------------------------
# 8. VFS `ls` handles Open Valstorm list response without crashing
# ---------------------------------------------------------------------------

def test_vfs_ls_handles_open_valstorm_list_tree(monkeypatch):
    client = MagicMock()
    client.get.return_value = httpx.Response(
        200,
        json=[{"id": "vaul_1", "name": "Engineering", "children": [{"id": "vaul_2", "name": "RFCs"}]}],
    )
    _patch_auth_with_sdk(monkeypatch, client_mock=client)

    res = runner.invoke(app, ["vfs", "ls"])
    assert res.exit_code == 0, res.output
    assert "Engineering" in res.output
    assert "RFCs" in res.output


# ---------------------------------------------------------------------------
# 9. Multi-Org `init` Layout, `open`, `bundler`, and `manifest_builder`
# ---------------------------------------------------------------------------

def test_init_creates_self_contained_org_layout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    res = runner.invoke(app, ["init", "acme-prod", "--profile", "acme", "--env", "prod"])
    assert res.exit_code == 0, res.output

    org_dir = tmp_path / "acme-prod"
    assert (org_dir / "valstorm.json").is_file()
    cfg = json.loads((org_dir / "valstorm.json").read_text())
    assert cfg["name"] == "acme-prod"
    assert cfg["profile"] == "acme"
    assert cfg["env"] == "prod"
    assert cfg["objects"] == [
        "app",
        "record_trigger",
        "function",
        "schedule_trigger_setting",
        "permission",
        "role",
    ]
    assert ".valstorm/" in (org_dir / ".gitignore").read_text()

    expected_dirs = {
        "schemas",
        "app",
        "record_trigger",
        "function",
        "schedule_trigger_setting",
        "permission",
        "role",
    }
    created_dirs = {p.name for p in org_dir.iterdir() if p.is_dir()}
    assert created_dirs == expected_dirs
    assert not (org_dir / "api_trigger").exists()
    assert not (org_dir / "queries").exists()
    assert not (org_dir / "valstorm_platform").exists()
    assert not (org_dir / ".mcp.json").exists()
    assert not (org_dir / "CLAUDE.md").exists()


def test_init_minimal_and_ai_flags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    res_min = runner.invoke(app, ["init", "bare-org", "--minimal"])
    assert res_min.exit_code == 0, res_min.output
    bare = tmp_path / "bare-org"
    assert (bare / "valstorm.json").is_file()
    assert (bare / ".gitignore").is_file()
    assert [p for p in bare.iterdir() if p.is_dir()] == []

    res_ai = runner.invoke(app, ["init", "ai-org", "--ai", "--url", "https://api.acme.internal"])
    assert res_ai.exit_code == 0, res_ai.output
    ai_dir = tmp_path / "ai-org"
    mcp_cfg = json.loads((ai_dir / ".mcp.json").read_text())
    assert mcp_cfg["mcpServers"]["valstorm"]["command"] == "uvx"
    assert mcp_cfg["mcpServers"]["valstorm"]["env"]["VALSTORM_API_URL"] == "https://api.acme.internal"
    assert (ai_dir / "CLAUDE.md").is_file()


def test_pull_defaults_to_standard_six_objects_without_api_trigger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res_init = runner.invoke(app, ["init", "org-a"])
    assert res_init.exit_code == 0
    monkeypatch.chdir(tmp_path / "org-a")

    sdk = MagicMock()
    sdk.apps.pull_metadata.return_value = {"schemas": {}, "objects": {}}
    _patch_auth_with_sdk(monkeypatch, sdk_mock=sdk)

    res_pull = runner.invoke(app, ["pull", "--force"])
    assert res_pull.exit_code == 0, res_pull.output
    called_types = sdk.apps.pull_metadata.call_args.kwargs["object_types"]
    assert called_types == [
        "app",
        "record_trigger",
        "function",
        "schedule_trigger_setting",
        "permission",
        "role",
    ]
    assert "api_trigger" not in called_types


def test_bundler_and_manifest_builder_use_org_api_name_layout(tmp_path):
    from valstorm_cli.bundler import bundle_local_app
    from valstorm_cli.manifest_builder import build_manifest_from_files

    org_dir = tmp_path / "my-org"
    for d in ("schemas", "function", "record_trigger", "role", "permission", "schedule_trigger_setting"):
        (org_dir / d).mkdir(parents=True)

    (org_dir / "valstorm.json").write_text(json.dumps({"name": "my-org", "env": "prod", "profile": "default"}))
    s_file = org_dir / "schemas" / "contact.json"
    s_file.write_text(json.dumps({"api_name": "contact", "title": "Contact"}))
    fn_file = org_dir / "function" / "sync.py"
    fn_file.write_text("def run():\n    return 1\n")
    role_file = org_dir / "role" / "admin.json"
    role_file.write_text(json.dumps({"name": "Admin"}))
    sched_file = org_dir / "schedule_trigger_setting" / "nightly.json"
    sched_file.write_text(json.dumps({"name": "Nightly"}))

    bundle = bundle_local_app(org_dir)
    assert bundle["name"] == "my-org"
    assert len(bundle["schemas"]) == 1
    assert bundle["records"]["function"][0]["code"] == "def run():\n    return 1\n"
    assert bundle["records"]["role"][0]["name"] == "Admin"
    assert bundle["records"]["schedule_trigger_setting"][0]["name"] == "Nightly"

    manifest = build_manifest_from_files({s_file, fn_file, role_file, sched_file}, org_dir)
    assert manifest == {
        "schemas": ["contact"],
        "objects": {
            "function": ["sync.py"],
            "role": ["admin.json"],
            "schedule_trigger_setting": ["nightly.json"],
        },
    }


def test_top_level_open_command(monkeypatch):
    client = MagicMock()
    client.post.return_value = httpx.Response(200, json={"code": "exch_123"})
    fake_auth = _patch_auth_with_sdk(monkeypatch, client_mock=client)
    fake_auth.profile = "acme"
    fake_auth.web_base_url = "https://app.acme.internal"

    opened = []
    monkeypatch.setattr("valstorm_cli.main.webbrowser.open", lambda url: opened.append(url))

    res = runner.invoke(app, ["open"])
    assert res.exit_code == 0, res.output
    assert opened == ["https://app.acme.internal/cli-login?code=exch_123"]
