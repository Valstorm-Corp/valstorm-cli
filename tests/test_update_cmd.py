"""Unit tests for valstorm update command and external dependency resolution."""

from pathlib import Path
import re
import subprocess
import pytest

from valstorm_cli import main as cli_main


CLI_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = CLI_ROOT / "pyproject.toml"


def test_cli_pyproject_declares_git_urls_for_internal_packages():
    """Ensure valstorm-client and valstorm-mcp-server have public GitHub URLs for external users."""
    content = PYPROJECT_PATH.read_text()
    stripped = re.sub(r"(?ms)\n\[tool\.uv\.sources\].*?(?=\n\[|\Z)", "", content)

    assert "valstorm-mcp-server @ git+https://github.com/Valstorm-Corp/valstorm-mcp.git" in stripped
    assert "valstorm-client @ git+https://github.com/Valstorm-Corp/valstorm-client-python.git" in stripped
    assert "allow-direct-references = true" in stripped


def test_cli_update_uv_tool_upgrade_fallback_on_failure(monkeypatch):
    """When uv tool upgrade valstorm-cli fails, falls back to uv tool install --from public git with --with deps."""
    monkeypatch.setattr(cli_main, "__file__", "/Users/test/.local/share/uv/tools/valstorm-cli/lib/python3.12/site-packages/valstorm_cli/main.py")
    monkeypatch.setattr(cli_main.sys, "executable", "/Users/test/.local/share/uv/tools/valstorm-cli/bin/python")
    monkeypatch.setattr(cli_main.shutil, "which", lambda cmd: "/usr/local/bin/uv" if cmd == "uv" else None)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd == ["uv", "tool", "upgrade", "valstorm-cli"]:
            raise subprocess.CalledProcessError(1, cmd, stderr=b"valstorm-client was not found")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)
    cli_main.update()

    assert len(calls) == 2
    assert calls[0] == ["uv", "tool", "upgrade", "valstorm-cli"]
    fallback_cmd = calls[1]
    assert fallback_cmd[:3] == ["uv", "tool", "install"]
    assert "git+https://github.com/Valstorm-Corp/valstorm-cli.git" in fallback_cmd
    assert "git+https://github.com/Valstorm-Corp/valstorm-client-python.git" in fallback_cmd
    assert "git+https://github.com/Valstorm-Corp/valstorm-mcp.git" in fallback_cmd
    assert "--force" in fallback_cmd
    assert "--upgrade" in fallback_cmd


def test_cli_update_pip_fallback_uses_public_repos(monkeypatch):
    """When not a uv tool, pip upgrade uses public GitHub repos and never private monorepo.git."""
    monkeypatch.setattr(cli_main, "__file__", "/usr/local/lib/python3.12/site-packages/valstorm_cli/main.py")
    monkeypatch.setattr(cli_main.sys, "executable", "/usr/local/bin/python3")
    monkeypatch.setattr(cli_main.shutil, "which", lambda cmd: None)

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(cli_main.subprocess, "run", fake_run)
    cli_main.update()

    assert len(calls) == 1
    cmd_str = " ".join(calls[0])
    assert "monorepo.git" not in cmd_str
    assert "git+https://github.com/Valstorm-Corp/valstorm-client-python.git" in calls[0]
    assert "git+https://github.com/Valstorm-Corp/valstorm-mcp.git" in calls[0]
    assert "git+https://github.com/Valstorm-Corp/valstorm-cli.git" in calls[0]
