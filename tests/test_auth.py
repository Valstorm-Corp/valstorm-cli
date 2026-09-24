import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
import pytest

from valstorm_cli.auth import get_auth, get_auth_file, ValstormAuth
from valstorm_cli.main import app

runner = CliRunner()


def test_get_auth_new_profile_not_overwritten(tmp_path, monkeypatch):
    """Ensure initializing an uncreated profile does not mutate profile to 'default'."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    valstorm_dir = tmp_path / ".valstorm"
    valstorm_dir.mkdir(parents=True, exist_ok=True)

    # Pre-populate default profile
    default_auth_file = valstorm_dir / "auth_prod_default.json"
    default_auth_file.write_text(json.dumps({
        "access_token": "default_access_token",
        "refresh_token": "default_refresh_token",
        "organization_name": "Default Org"
    }))

    # Request new 'admin' profile
    auth = get_auth(profile="admin", env="prod")
    assert auth.profile == "admin"
    assert auth.env == "prod"
    assert auth.auth_file.name == "auth_prod_admin.json"
    assert auth.access_token is None

    # Saving tokens creates auth_prod_admin.json without modifying default
    auth.save_tokens(
        access_token="admin_token",
        refresh_token="admin_refresh",
        organization_name="Admin Org",
        user={"name": "Admin", "email": "admin@valstorm.com"}
    )

    admin_file = valstorm_dir / "auth_prod_admin.json"
    assert admin_file.exists()
    admin_data = json.loads(admin_file.read_text())
    assert admin_data["access_token"] == "admin_token"
    assert admin_data["organization_name"] == "Admin Org"
    assert admin_data["user"]["email"] == "admin@valstorm.com"

    # Default file remains intact
    default_data = json.loads(default_auth_file.read_text())
    assert default_data["access_token"] == "default_access_token"
    assert default_data["organization_name"] == "Default Org"


def test_get_auth_file_legacy_fallback(tmp_path, monkeypatch):
    """Ensure default profile can resolve legacy auth_{env}.json and auth.json."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    valstorm_dir = tmp_path / ".valstorm"
    valstorm_dir.mkdir(parents=True, exist_ok=True)

    # No files exist -> returns standard pattern
    assert get_auth_file("prod", "default").name == "auth_prod_default.json"
    assert get_auth_file("prod", "admin").name == "auth_prod_admin.json"

    # Legacy auth_prod.json exists
    legacy_file = valstorm_dir / "auth_prod.json"
    legacy_file.write_text(json.dumps({"access_token": "legacy_token"}))
    assert get_auth_file("prod", "default").name == "auth_prod.json"

    # Standard auth_prod_default.json takes precedence once created
    std_file = valstorm_dir / "auth_prod_default.json"
    std_file.write_text(json.dumps({"access_token": "std_token"}))
    assert get_auth_file("prod", "default").name == "auth_prod_default.json"


def test_list_profiles_deduplication(tmp_path, monkeypatch):
    """Ensure list_profiles deduplicates duplicate env/profile files."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    valstorm_dir = tmp_path / ".valstorm"
    valstorm_dir.mkdir(parents=True, exist_ok=True)

    # Create both standard and legacy default
    (valstorm_dir / "auth_prod_default.json").write_text(json.dumps({
        "access_token": "tok1",
        "organization_name": "Standard Default Org",
        "user": {"name": "User 1", "email": "user1@valstorm.com"}
    }))
    (valstorm_dir / "auth_prod.json").write_text(json.dumps({
        "access_token": "tok2",
        "organization_name": "Legacy Default Org"
    }))
    # Create admin
    (valstorm_dir / "auth_prod_admin.json").write_text(json.dumps({
        "access_token": "tok3",
        "organization_name": "Admin Org",
        "user": {"name": "Admin", "email": "admin@valstorm.com"}
    }))

    result = runner.invoke(app, ["auth", "list"])
    assert result.exit_code == 0
    # Should list both admin and default, but default only once
    assert "Profile: admin" in result.output
    assert "Profile: default" in result.output
    assert result.output.count("Profile: default") == 1


@patch("valstorm_cli.auth_cmds.get_pkce_pair", return_value=("mock_verifier", "mock_challenge"))
@patch("valstorm_cli.auth_cmds.webbrowser.open")
def test_login_oauth_targets_correct_profile(mock_open, mock_pkce, tmp_path, monkeypatch):
    """Ensure valstorm auth login -p admin -e prod targets admin profile and saves tokens correctly."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    valstorm_dir = tmp_path / ".valstorm"
    valstorm_dir.mkdir(parents=True, exist_ok=True)

    # Pre-populate default profile
    default_auth_file = valstorm_dir / "auth_prod_default.json"
    default_auth_file.write_text(json.dumps({
        "access_token": "original_default_token",
        "organization_name": "Default Org"
    }))

    # Mock httpx.Client in auth_cmds
    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json = json_data
            self.text = json.dumps(json_data)

        def json(self):
            return self._json

    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            if "/oauth2/token" in url:
                return MockResponse(200, {
                    "access_token": "new_admin_access_token",
                    "refresh_token": "new_admin_refresh_token"
                })
            return MockResponse(404, {})

        def get(self, url, **kwargs):
            if "/auth/load" in url:
                return MockResponse(200, {
                    "user": {
                        "id": "usr_admin",
                        "name": "Admin Boss",
                        "email": "admin@valstorm.com",
                        "organization_name": "Admin Org",
                        "organization_id": "org_admin"
                    }
                })
            return MockResponse(404, {})

    # Mock the callback server to immediately return auth_code
    class MockServer:
        def __init__(self, *args, **kwargs):
            pass

        @property
        def state(self):
            return "mock_state"

        @state.setter
        def state(self, val):
            pass

        @property
        def auth_code(self):
            return "mock_auth_code_123"

        @auth_code.setter
        def auth_code(self, val):
            pass

        def serve_forever(self):
            pass

        def shutdown(self):
            pass

        def server_close(self):
            pass

    monkeypatch.setattr("valstorm_cli.auth_cmds.ReusableHTTPServer", MockServer)
    monkeypatch.setattr("valstorm_cli.auth_cmds.secrets.token_urlsafe", lambda n: "mock_state")
    monkeypatch.setattr("httpx.Client", MockHttpxClient)
    monkeypatch.setattr("valstorm_cli.auth.httpx.Client", MockHttpxClient)

    result = runner.invoke(app, ["auth", "login", "-p", "admin", "-e", "prod"])
    assert result.exit_code == 0, f"Command failed with output: {result.output}"
    assert "Profile: admin" in result.output
    assert "Successfully logged in!" in result.output

    # Verify admin file was created
    admin_auth_file = valstorm_dir / "auth_prod_admin.json"
    assert admin_auth_file.exists()
    admin_data = json.loads(admin_auth_file.read_text())
    assert admin_data["access_token"] == "new_admin_access_token"
    assert admin_data["refresh_token"] == "new_admin_refresh_token"
    assert admin_data["organization_name"] == "Admin Org"
    assert admin_data["user"]["name"] == "Admin Boss"

    # Verify default file was NEVER overwritten
    default_data = json.loads(default_auth_file.read_text())
    assert default_data["access_token"] == "original_default_token"
    assert default_data["organization_name"] == "Default Org"

