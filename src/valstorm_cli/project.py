import typer
import shutil
import os
import json
import webbrowser
import httpx
from pathlib import Path
from rich.console import Console
from .auth import get_auth, get_web_url, get_project_root, load_config

console = Console()
project_app = typer.Typer(help="Manage local workspace settings and stubs.")







def _build_mcp_server_config(env: str, profile: str) -> dict:
    return {
        "command": "uv",
        "args": ["run", "--directory", ".", "python", "run_mcp.py"],
        "env": {
            "VALSTORM_ENV": env,
            "VALSTORM_PROFILE": profile,
            "VIRTUAL_ENV": "",
        },
    }

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except (json.JSONDecodeError, IOError):
        return {}

DEFAULT_CLAUDE_PERMISSIONS = [
    "Bash(uv:*)",
    "Bash(valstorm:*)",
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "mcp__valstorm__get_me",
    "mcp__valstorm__get_status",
    "mcp__valstorm__get_environment",
    "mcp__valstorm__list_accounts",
    "mcp__valstorm__list_schemas",
    "mcp__valstorm__get_schema",
    "mcp__valstorm__run_sql_query",
]

DEFAULT_GEMINI_HOOKS = {
    "SessionStart": [
        {
            "matcher": ".*",
            "hooks": [
                {
                    "name": "inject-docs",
                    "type": "command",
                    "command": "python3 valstorm_platform/hooks/inject_docs.py",
                }
            ],
        }
    ]
}

def _write_ai_configs(target_path: Path, env: str, profile: str, silent: bool = False):
    server_config = _build_mcp_server_config(env, profile)

    mcp_path = target_path / ".mcp.json"
    mcp_data = _load_json(mcp_path)
    mcp_data.setdefault("mcpServers", {})
    mcp_data["mcpServers"]["valstorm"] = server_config
    with open(mcp_path, "w") as f:
        json.dump(mcp_data, f, indent=4)

    claude_dir = target_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    claude_path = claude_dir / "settings.json"
    claude_data = _load_json(claude_path)
    permissions = claude_data.setdefault("permissions", {})
    existing_allow = permissions.get("allow", [])
    seen = set(existing_allow)
    merged = list(existing_allow)
    for perm in DEFAULT_CLAUDE_PERMISSIONS:
        if perm not in seen:
            merged.append(perm)
            seen.add(perm)
    permissions["allow"] = merged
    with open(claude_path, "w") as f:
        json.dump(claude_data, f, indent=4)

    gemini_dir = target_path / ".gemini"
    gemini_dir.mkdir(exist_ok=True)
    gemini_path = gemini_dir / "settings.json"
    gemini_data = _load_json(gemini_path)
    gemini_data.setdefault("mcpServers", {})
    gemini_data["mcpServers"]["valstorm"] = server_config
    if "hooks" not in gemini_data:
        gemini_data["hooks"] = DEFAULT_GEMINI_HOOKS
    with open(gemini_path, "w") as f:
        json.dump(gemini_data, f, indent=4)

    if not silent:
        console.print(
            "[green]✓[/green] AI assistant configs refreshed "
            "([cyan].mcp.json[/cyan], [cyan].claude/settings.json[/cyan], [cyan].gemini/settings.json[/cyan])."
        )
def update_local_stubs(target_path: Path, silent: bool = False):
    """Copies all platform assets (stubs and documentation) from the CLI package to the project."""
    platform_dir = target_path / "valstorm_platform"
    platform_dir.mkdir(exist_ok=True)
    
    # Ensure __init__.py exists
    init_file = platform_dir / "__init__.py"
    if not init_file.exists():
        with open(init_file, "w") as f:
            f.write("# Valstorm Platform SDK\n")
            
    current_dir = Path(__file__).parent
    source_assets_dir = current_dir / "stubs"
    
    if source_assets_dir.exists():
        # Recursively copy all files from stubs/ to valstorm_platform/
        for root, dirs, files in os.walk(source_assets_dir):
            # Calculate relative path from source_assets_dir
            rel_path = Path(root).relative_to(source_assets_dir)
            dest_root = platform_dir / rel_path
            dest_root.mkdir(parents=True, exist_ok=True)
            
            for file in files:
                if file.endswith(".pyc") or file == "__pycache__":
                    continue
                
                source_file = Path(root) / file
                dest_file = dest_root / file
                
                # Check if an update is needed
                needs_update = True
                if dest_file.exists():
                    # For performance, we could check mtime, but content check is safer for stubs
                    # Actually, for large files or many files, mtime is better.
                    if source_file.stat().st_mtime <= dest_file.stat().st_mtime:
                        needs_update = False
                
                if needs_update:
                    shutil.copy2(source_file, dest_file)
        
        if not silent:
            console.print("[green]✓[/green] Valstorm platform assets (stubs & docs) synced.")
    elif not silent:
        console.print("[yellow]![/yellow] Warning: Could not find built-in platform assets to copy.")

@project_app.command(name="update-stubs")
def update_stubs_command(
    skip_configs: bool = typer.Option(False, "--skip-configs", help="Only refresh stubs/docs; skip AI assistant config refresh."),
):
    """
    Update local platform assets and AI assistant configs to the latest CLI version.

    Refreshes:
    - PlatformContext stubs and platform docs under `valstorm_platform/`.
    - `.mcp.json` (Claude Code MCP server registration).
    - `.claude/settings.json` permissions allowlist (merged — preserves your additions).
    - `.gemini/settings.json` mcpServers entry (merged — preserves other servers).

    Does NOT touch CLAUDE.md / GEMINI.md / README.md — those are yours to edit.
    """
    root = get_project_root()
    update_local_stubs(root)

    if skip_configs:
        return

    try:
        config = load_config(root)
    except Exception as e:
        console.print(f"[yellow]![/yellow] Could not read valstorm.json ({e}); skipping AI config refresh.")
        return

    env = config.get("env") or "prod"
    profile = config.get("profile") or "default"
    _write_ai_configs(root, env=env, profile=profile)

@project_app.command(name="open")
def open_browser(
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    Open the Valstorm web application in your browser, pre-authenticated.
    """
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        try:
            # 1. Get Exchange Token from API
            res = client.post("/auth/cli-browser-token")
            if res.status_code != 200:
                console.print(f"[bold red]Failed to generate browser token:[/bold red] {res.text}")
                raise typer.Exit(1)
            
            exchange_code = res.json()["exchange_code"]

            # 2. Build Web URL
            base_web_url = get_web_url(auth.env)
            # Remove trailing slash if present
            if base_web_url.endswith("/"):
                base_web_url = base_web_url[:-1]

            target_url = f"{base_web_url}/cli-login?code={exchange_code}"

            console.print(f"Opening [bold blue]{base_web_url}[/bold blue] as [bold cyan]{auth.profile}[/bold cyan]...")
            webbrowser.open(target_url)
            
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

