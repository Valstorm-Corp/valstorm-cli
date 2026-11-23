import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console

from .app_cmds import app_cmds
from .auth import get_api_base_url, get_auth, get_base_url
from .auth_cmds import auth_app
from .auth_cmds import login as auth_login
from .fn_cmds import fn_app
from .project import _write_ai_configs, project_app, update_local_stubs
from .query import graphql, sql
from .record import record_app
from .rpc_cmds import rpc_app
from .sandbox import sandbox_app
from .schema import schema_app
from .search_cmds import ask_command, search_command
from .sync import pull, push
from .vfs_cmds import vfs_app

app = typer.Typer(
    help="Open Valstorm Developer CLI.",
    no_args_is_help=True,
)
console = Console()

# Subcommand groups
app.add_typer(auth_app, name="auth")
app.add_typer(project_app, name="project")
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

    # Check if running from local editable monorepo
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


@app.command()
def init(
    name: Optional[str] = typer.Argument(None, help="Directory name to create (defaults to current directory)."),
    env: str = typer.Option("prod", "--env", "-e", help="Target environment (prod, dev, local)."),
    profile: str = typer.Option("default", "--profile", "-p", help="Auth profile to bind to this workspace."),
    url: Optional[str] = typer.Option(None, "--url", "--api-url", help="Optional custom Open Valstorm API URL."),
    app_id: Optional[str] = typer.Option(None, "--app", "-a", help="Optional default App ID for this workspace."),
    skip_ai_configs: bool = typer.Option(False, "--skip-ai-configs", help="Skip generating AI IDE configs (.mcp.json, .claude, .gemini)."),
):
    """
    Initialize a new Open Valstorm developer workspace.
    """
    target_path = Path(name) if name else Path.cwd()
    if name:
        target_path.mkdir(parents=True, exist_ok=True)

    # 1. Standard workspace directories
    for folder in ("schemas", "function", "record_trigger", "api_trigger", "queries"):
        (target_path / folder).mkdir(exist_ok=True)

    # 2. Write valstorm.json
    config_file = target_path / "valstorm.json"
    config: dict = {
        "name": target_path.name,
        "env": env.lower(),
        "profile": profile.lower(),
    }
    if url:
        config["api_url"] = url.strip().rstrip("/")
    if app_id:
        config["app_id"] = app_id

    if not config_file.exists():
        config_file.write_text(json.dumps(config, indent=4) + "\n", encoding="utf-8")
        console.print(f"[green]✓[/green] Created {config_file.name}")

    # 3. Sync PlatformContext stubs
    update_local_stubs(target_path)

    # 4. Write concise workspace README & AI guide
    readme_file = target_path / "README.md"
    if not readme_file.exists():
        readme_file.write_text(
            f"# {target_path.name}\n\n"
            "Open Valstorm workspace.\n\n"
            "## Quick Start\n\n"
            "```bash\n"
            "valstorm login\n"
            "valstorm pull\n"
            "valstorm schema status\n"
            "valstorm fn validate function/my_fn.py\n"
            "valstorm push --dry-run\n"
            "```\n",
            encoding="utf-8",
        )

    ai_guide = (
        "# Open Valstorm Workspace Guide\n\n"
        "## Core CLI Commands\n"
        "- `valstorm pull [--schemas-only] [--type function]` — Pull metadata & schemas in one roundtrip.\n"
        "- `valstorm push [--dry-run] [--diff origin/main]` — Push local changes in a single ACID transaction.\n"
        "- `valstorm schema list | get | status | sync` — Inspect schemas and sync native PostgreSQL migrations.\n"
        "- `valstorm sql \"SELECT id, name FROM contact LIMIT 10\"` — Query data (raw IDs by default; pass `--hydrate` for `{id, name}`).\n"
        "- `valstorm graphql \"{ contact(limit: 5) { id name } }\"` — Run GraphQL queries (raw IDs by default; pass `--hydrate` for `{id, name}`).\n"
        "- `valstorm fn validate <file.py>` / `valstorm fn run <target>` — AST-validate and execute serverless functions.\n"
        "- `valstorm rpc list` / `valstorm rpc call <target>` — Discover and invoke PlatformContext and plugin methods.\n"
        "- `valstorm app list | install | deploy | promote | publish` — Manage Valstorm apps.\n"
        "- `valstorm vfs ls | upload | download | mv | rm | info | index` — Manage VFS vaults and files.\n"
    )
    for guide_name in ("CLAUDE.md", "GEMINI.md"):
        guide_file = target_path / guide_name
        if not guide_file.exists():
            guide_file.write_text(ai_guide, encoding="utf-8")

    # 5. Optional AI IDE configs
    if not skip_ai_configs:
        _write_ai_configs(target_path, env=env.lower(), profile=profile.lower())

    console.print(f"\n[bold green]✓ Open Valstorm workspace initialized at {target_path.resolve()}[/bold green]")


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
