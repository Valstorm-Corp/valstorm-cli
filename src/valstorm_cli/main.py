import importlib.metadata
import json
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console

from .app_cmds import app_cmds
from .auth import ValstormAuth, get_api_base_url, get_auth, get_base_url, requires_auth
from .auth_cmds import auth_app
from .auth_cmds import login as auth_login
from .fn_cmds import fn_app
from .query import graphql, sql
from .record import record_app
from .rpc_cmds import rpc_app
from .sandbox import sandbox_app
from .schema import schema_app
from .search_cmds import ask_command, search_command
from .sync import STANDARD_OBJECTS, pull, push
from .vfs_cmds import vfs_app

app = typer.Typer(
    help="Open Valstorm Developer CLI.",
    no_args_is_help=True,
)
console = Console()

# Subcommand groups
app.add_typer(auth_app, name="auth")
app.add_typer(schema_app, name="schema")
app.add_typer(record_app, name="record")
app.add_typer(fn_app, name="fn")
app.add_typer(app_cmds, name="app")
app.add_typer(sandbox_app, name="sandbox")
app.add_typer(vfs_app, name="vfs")
app.add_typer(rpc_app, name="rpc")

# Top-level ergonomic shortcuts
app.command(name="pull", help="Pull workspace metadata and schemas via /v1/apps/metadata/pull.")(pull)
app.command(name="push", help="Push workspace metadata and schemas atomically via /v1/apps/metadata/push.")(push)
app.command(name="sql", help="Execute a SQL query (raw IDs by default; pass --hydrate for {id, name}).")(sql)
app.command(name="graphql", help="Execute a GraphQL query (raw IDs by default; pass --hydrate for {id, name}).")(graphql)
app.command(name="search", help="Search files, metadata, and document vector chunks across the workspace.")(search_command)
app.command(name="ask", help="Ask natural language questions grounded in workspace documents with streaming AI answers.")(ask_command)


@app.command(name="login")
def login(
    method: Optional[str] = typer.Argument(None, help="Login method, e.g., 'pat'"),
    key: Optional[str] = typer.Argument(None, help="The token/key for the given method"),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name to save these credentials under."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment (local, dev, prod, or custom label)."),
    url: Optional[str] = typer.Option(None, "--url", "--api-url", help="Custom self-hosted Open Valstorm API base URL."),
    web_url: Optional[str] = typer.Option(None, "--web-url", help="Custom web app URL for browser OAuth login."),
    use_password: bool = typer.Option(False, "--password", help="Use password flow."),
    pat: str = typer.Option(None, "--pat", "--token", help="Login using a Personal Access Token (PAT)."),
    refresh_token: Optional[str] = typer.Option(None, "--refresh-token", "-r", help="Optional refresh token."),
):
    """
    Authenticate with Valstorm (shortcut for `valstorm auth login`).
    """
    auth_login(
        method=method,
        key=key,
        profile=profile,
        env=env,
        url=url,
        web_url=web_url,
        use_password=use_password,
        pat=pat,
        refresh_token=refresh_token,
    )


@app.command(name="open")
@requires_auth
def open_browser(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
    auth: ValstormAuth = None,  # type: ignore
):
    """
    Open the Valstorm web app in your default browser logged in as the current org/profile.
    """
    try:
        res = client.post("/auth/cli-browser-token")
        if res.status_code != 200:
            console.print(f"[bold red]Failed to generate browser session ({res.status_code}):[/bold red] {res.text}")
            raise typer.Exit(1)
        exchange_code = res.json().get("code")
    except httpx.RequestError as e:
        console.print(f"[bold red]Connection Error:[/bold red] {e}")
        raise typer.Exit(1)

    base_web_url = auth.web_base_url.rstrip("/")
    target_url = f"{base_web_url}/cli-login?code={exchange_code}"
    console.print(f"Opening [bold blue]{base_web_url}[/bold blue] as [bold cyan]{auth.profile}[/bold cyan]...")
    webbrowser.open(target_url)


@app.command()
def status(
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment (prod, dev, local)."),
    url: Optional[str] = typer.Option(None, "--url", "--api-url", help="Custom Open Valstorm API base URL."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
):
    """
    Check if the target Valstorm API is live and reachable.
    """
    auth = get_auth(profile=profile, env=env, api_url=url)
    base_url = get_base_url(env=auth.env, api_url=url or auth.api_url)
    api_url = get_api_base_url(env=auth.env, api_url=url or auth.api_url)
    console.print(f"Checking API status at [bold blue]{api_url}[/bold blue]...")

    try:
        response = httpx.get(f"{base_url}/v1/health", timeout=5.0)
        if response.status_code != 200:
            response = httpx.get(f"{base_url}/status", timeout=5.0)

        if response.status_code == 200:
            console.print("[bold green]✓ Valstorm API is LIVE![/bold green]")
            try:
                console.print(response.json())
            except Exception:
                console.print(response.text)
        else:
            console.print(f"[bold red]✗ Valstorm API returned status code {response.status_code}[/bold red]")
            raise typer.Exit(1)
    except httpx.RequestError as exc:
        console.print(f"[bold red]✗ Failed to connect to Valstorm API:[/bold red] {exc}")
        raise typer.Exit(1)


@app.command()
def update():
    """
    Update the Valstorm CLI to the latest version.
    """
    console.print("[bold blue]Checking for Valstorm CLI updates...[/bold blue]")

    cli_repo_url = "git+https://github.com/Valstorm-Corp/valstorm-cli.git"
    client_repo_url = "git+https://github.com/Valstorm-Corp/valstorm-client-python.git"

    cli_path = Path(__file__).resolve()
    exe_path = Path(sys.executable).resolve()

    is_uv_tool = "uv/tools" in str(cli_path) or "uv/tools" in str(exe_path)

    if is_uv_tool and shutil.which("uv"):
        console.print("Detected [cyan]uv tool[/cyan] installation. Upgrading...")
        try:
            subprocess.run(["uv", "tool", "upgrade", "valstorm-cli"], check=True)
            console.print("[bold green]✓ Valstorm CLI successfully updated via uv![/bold green]")
            return
        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]uv tool upgrade failed ({e}), retrying with public git repos...[/yellow]")
            try:
                subprocess.run(
                    [
                        "uv",
                        "tool",
                        "install",
                        "--force",
                        "--upgrade",
                        "--with",
                        client_repo_url,
                        cli_repo_url,
                    ],
                    check=True,
                )
                console.print("[bold green]✓ Valstorm CLI successfully updated via uv![/bold green]")
                return
            except subprocess.CalledProcessError as fallback_err:
                console.print(f"[bold red]uv tool update failed:[/bold red] {fallback_err}")
                raise typer.Exit(1)

    if "monorepo" in str(cli_path) and "apps/cli" in str(cli_path):
        console.print("[yellow]Detected local monorepo development installation.[/yellow]")
        console.print("Pull the latest git changes and run [cyan]uv sync --project apps/cli[/cyan] to update.")
        return

    console.print("Upgrading via [cyan]pip[/cyan]...")
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                client_repo_url,
                cli_repo_url,
            ],
            check=True,
        )
        console.print("[bold green]✓ Valstorm CLI successfully updated![/bold green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Update failed:[/bold red] {e}")
        raise typer.Exit(1)


def _ensure_gitignore_entry(target_path: Path, entry: str = ".valstorm/") -> None:
    gitignore = target_path / ".gitignore"
    if gitignore.exists():
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        if any(line.strip() == entry for line in lines):
            return
        prefix = "\n" if lines and lines[-1] != "" else ""
        with open(gitignore, "a", encoding="utf-8") as fh:
            fh.write(f"{prefix}{entry}\n")
    else:
        gitignore.write_text(f"{entry}\n", encoding="utf-8")


def _write_optional_ai_files(target_path: Path, env: str, profile: str, api_url: Optional[str]) -> None:
    mcp_env: dict[str, str] = {"VALSTORM_ENV": env, "VALSTORM_PROFILE": profile}
    if api_url:
        mcp_env["VALSTORM_API_URL"] = api_url
    mcp_cfg = {
        "mcpServers": {
            "valstorm": {
                "command": "uvx",
                "args": [
                    "--from",
                    "git+https://github.com/Valstorm-Corp/valstorm-mcp.git",
                    "valstorm-mcp",
                ],
                "env": mcp_env,
            }
        }
    }
    mcp_file = target_path / ".mcp.json"
    if not mcp_file.exists():
        mcp_file.write_text(json.dumps(mcp_cfg, indent=2) + "\n", encoding="utf-8")
        console.print(f"[green]✓[/green] Created {mcp_file.name}")

    claude_file = target_path / "CLAUDE.md"
    if not claude_file.exists():
        claude_file.write_text(
            "# Open Valstorm Workspace Guide\n\n"
            "## Core CLI Commands\n"
            "- `valstorm pull [--schemas-only] [--type <api_name>] [--all]` — Pull org metadata & schemas.\n"
            "- `valstorm push [--dry-run] [--diff origin/main]` — Push local changes in a single ACID transaction.\n"
            "- `valstorm schema list | get | status | sync` — Inspect schemas and sync native PostgreSQL migrations.\n"
            "- `valstorm sql \"SELECT id, name FROM contact LIMIT 10\"` — Query data (raw IDs by default; pass `--hydrate` for `{id, name}`).\n"
            "- `valstorm graphql \"{ contact(limit: 5) { id name } }\"` — Run GraphQL queries (raw IDs by default; pass `--hydrate` for `{id, name}`).\n"
            "- `valstorm fn list | validate <file.py> | run <target>` — Validate and execute serverless functions.\n"
            "- `valstorm rpc list | call <target>` — Discover and invoke live PlatformContext & plugin methods.\n"
            "- `valstorm app list | install | deploy | promote | publish` — Manage Valstorm apps.\n"
            "- `valstorm vfs ls | upload | download | mv | rm | info | index` — Manage VFS vaults and files.\n"
            "- `valstorm open` — Open this org in your browser.\n",
            encoding="utf-8",
        )
        console.print(f"[green]✓[/green] Created {claude_file.name}")


@app.command()
def init(
    name: Optional[str] = typer.Argument(None, help="Org workspace folder name to create (defaults to current directory)."),
    env: str = typer.Option("prod", "--env", "-e", help="Target environment (prod, dev, local)."),
    profile: str = typer.Option("default", "--profile", "-p", help="Auth profile to bind to this org folder."),
    url: Optional[str] = typer.Option(None, "--url", "--api-url", help="Optional custom Open Valstorm API URL."),
    web_url: Optional[str] = typer.Option(None, "--web-url", help="Optional custom Open Valstorm web URL."),
    app_id: Optional[str] = typer.Option(None, "--app", "-a", help="Optional default App ID for this workspace."),
    minimal: bool = typer.Option(False, "--minimal", help="Only create valstorm.json and .gitignore (skip object directories)."),
    ai: bool = typer.Option(False, "--ai", help="Also generate opt-in .mcp.json (via uvx valstorm-mcp) and CLAUDE.md."),
):
    """
    Initialize a self-contained Open Valstorm org workspace directory.

    Places `valstorm.json` inside `<name>/` so each org you manage is isolated to its own folder.
    """
    target_path = Path(name) if name else Path.cwd()
    if name:
        target_path.mkdir(parents=True, exist_ok=True)

    # 1. Write org-scoped valstorm.json inside <name>/
    config_file = target_path / "valstorm.json"
    clean_api_url = url.strip().rstrip("/") if url else None
    clean_web_url = web_url.strip().rstrip("/") if web_url else None
    config: dict = {
        "name": target_path.name,
        "env": env.lower(),
        "profile": profile.lower(),
        "objects": list(STANDARD_OBJECTS),
    }
    if clean_api_url:
        config["api_url"] = clean_api_url
    if clean_web_url:
        config["web_url"] = clean_web_url
    if app_id:
        config["app_id"] = app_id

    if not config_file.exists():
        config_file.write_text(json.dumps(config, indent=4) + "\n", encoding="utf-8")
        console.print(f"[green]✓[/green] Created {config_file.name}")

    # 2. Ensure .valstorm/ is gitignored
    _ensure_gitignore_entry(target_path, ".valstorm/")

    # 3. Create canonical api_name directories (unless --minimal)
    if not minimal:
        for folder in ["schemas", *STANDARD_OBJECTS]:
            (target_path / folder).mkdir(exist_ok=True)

    # 4. Opt-in AI/MCP config
    if ai:
        _write_optional_ai_files(target_path, env=env.lower(), profile=profile.lower(), api_url=clean_api_url)

    console.print(f"\n[bold green]✓ Open Valstorm org workspace initialized at {target_path.resolve()}[/bold green]")
    if name:
        console.print(f"Next: [cyan]cd {name} && valstorm pull[/cyan]")
    else:
        console.print("Next: [cyan]valstorm pull[/cyan]")


def _get_version() -> str:
    try:
        return importlib.metadata.version("valstorm-cli")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


@app.command()
def version():
    """
    Display the installed Valstorm CLI version.
    """
    console.print(f"valstorm-cli [bold cyan]{_get_version()}[/bold cyan]")


def version_callback(value: bool):
    if value:
        console.print(f"valstorm-cli [bold cyan]{_get_version()}[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version_flag: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show the CLI version and exit.",
    ),
):
    """
    Open Valstorm Developer CLI.
    """
    return


if __name__ == "__main__":
    app()
