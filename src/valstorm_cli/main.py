import typer
import httpx
import json
import shutil
import subprocess
import sys
from typing import Optional
from pathlib import Path
from .auth import get_api_base_url, get_auth, get_project_root
from rich.console import Console


app = typer.Typer(help="Valstorm Developer CLI", no_args_is_help=True)
mcp_app = typer.Typer(help="Manage the Valstorm MCP Server")
manifest_app = typer.Typer(help="Manage Valstorm manifests")

app.add_typer(mcp_app, name="mcp")
app.add_typer(manifest_app, name="manifest")

from .auth_cmds import auth_app, login as auth_login
from .scaffold_cmds import scaffold_app
from .sync import pull_app, push_app
from .project import project_app
from .project import update_local_stubs, _write_ai_configs

app.add_typer(auth_app, name="auth")
app.add_typer(scaffold_app, name="scaffold")
app.add_typer(pull_app, name="pull")
app.add_typer(push_app, name="push")
app.add_typer(project_app, name="project")

@app.command(hidden=True)
def login(
    method: Optional[str] = typer.Argument(None, help="Login method, e.g., 'pat'"),
    key: Optional[str] = typer.Argument(None, help="The token/key for the given method"),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name to save these credentials under."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment (local, dev, prod)."),
    use_password: bool = typer.Option(False, "--password", help="Use legacy password flow."),
    pat: str = typer.Option(None, "--pat", help="Login using a Personal Access Token (PAT).")
):
    auth_login(method=method, key=key, profile=profile, env=env, use_password=use_password, pat=pat)


from .sandbox import sandbox_app
from .record import record_app
from .schema import schema_app
from .query import sql, graphql

app.add_typer(sandbox_app, name="sandbox")
app.add_typer(record_app, name="record")
app.add_typer(schema_app, name="schema")
app.command(name="sql")(sql)
app.command(name="graphql")(graphql)
console = Console()



@app.command()
def status():
    """
    Check the status of the Valstorm API.
    """
    url = f"{get_api_base_url()}/status"
    console.print(f"Checking status for [blue]{url}[/blue]...")
    
    try:
        response = httpx.get(url, timeout=10.0)
        
        if response.status_code == 200:
            console.print("[bold green]SUCCESS:[/bold green] API is running and responded with HTTP 200.")
            console.print(response.json())
        else:
            console.print(f"[bold yellow]WARNING:[/bold yellow] API responded with status code {response.status_code}")
            console.print(response.text)
            
    except httpx.RequestError as e:
        console.print(f"[bold red]ERROR:[/bold red] Could not connect to the API. {e}")
    except Exception as e:
        console.print(f"[bold red]UNEXPECTED ERROR:[/bold red] {e}")



@app.command()
def update():
    """
    Update the Valstorm CLI to the latest version from GitHub.
    """
    console.print("Updating Valstorm CLI to the latest version from GitHub...")
    repo_url = "git+https://github.com/Valstorm-Corp/valstorm-cli.git"
    
    try:
        # Check if installed as a uv tool first
        if shutil.which("uv"):
            res = subprocess.run(["uv", "tool", "list"], capture_output=True, text=True)
            if "valstorm-cli" in res.stdout:
                console.print("Detected installation as a [cyan]uv tool[/cyan]. Upgrading...")
                subprocess.run(["uv", "tool", "upgrade", "valstorm-cli"], check=True)
                console.print("[bold green]✓[/bold green] Valstorm CLI updated successfully.")
                return

        # Fallback to pip upgrade
        # We try uv pip install if uv is available, otherwise standard pip
        if shutil.which("uv"):
            console.print("Using [cyan]uv[/cyan] to upgrade...")
            cmd = ["uv", "pip", "install", "--upgrade", repo_url]
        else:
            console.print("Using [cyan]pip[/cyan] to upgrade...")
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", repo_url]
             
        subprocess.run(cmd, check=True)
        console.print("[bold green]✓[/bold green] Valstorm CLI updated successfully.")
        
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error during update:[/bold red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")
        raise typer.Exit(1)




@app.command()
def init(
    path: str = typer.Argument(None, help="Name of the directory to initialize the project in."),
    profile: str = typer.Option(None, "--profile", "-p", help="The auth profile to use."),
    env: str = typer.Option(None, "--env", "-e", help="The target environment.")
):
    """
    Initialize a new Valstorm development project.
    """
    target_path_str = path or typer.prompt("Enter a name for your new project folder")
    target_path = Path(target_path_str)
    
    if target_path.exists() and any(target_path.iterdir()):
        console.print(f"[yellow]Warning: Directory '{target_path}' already exists and is not empty.[/yellow]")
        if not typer.confirm("Do you want to continue initializing here?"):
            raise typer.Exit()
            
    target_path.mkdir(parents=True, exist_ok=True)
    
    # 0. Git Init
    try:
        import subprocess
        subprocess.run(["git", "init"], cwd=target_path, capture_output=True)
        console.print("[green]✓[/green] Git repository initialized.")
    except Exception as e:
        console.print(f"[yellow]![/yellow] Warning: Failed to initialize git repository: {e}")

    # 1. Configuration
    auth = get_auth(profile=profile, env=env)
    
    config = {
        "env": auth.env,
        "profile": auth.profile,
        "objects": [
            "record_trigger", "function", "ai_agent", "app", 
            "app_page", "app_metadata", "permission", 
            "notification_setting", "schedule_trigger_setting", "workspace"
        ]
    }
    
    with open(target_path / "valstorm.json", "w") as f:
        json.dump(config, f, indent=4)

    # 1.1 Create pyproject.toml for the new project
    toml_content = f"""[project]
name = "{target_path.name}"
version = "0.1.0"
description = "Valstorm development project"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "valstorm-cli @ git+https://github.com/Valstorm-Corp/valstorm-cli.git",
    "valstorm-mcp @ git+https://github.com/Valstorm-Corp/valstorm-mcp.git",
    "httpx>=0.27.0"
]
"""
    with open(target_path / "pyproject.toml", "w") as f:
        f.write(toml_content)

    # 1.2 Create .python-version
    with open(target_path / ".python-version", "w") as f:
        f.write("3.11\n")

    # 1.3 Create run_mcp.py entry point
    mcp_wrapper = """from valstorm_mcp.main import mcp
import os

if __name__ == "__main__":
    mcp.run()
"""
    with open(target_path / "run_mcp.py", "w") as f:
        f.write(mcp_wrapper)
    
    # 2. Create Directory Structure
    object_dir = target_path / "object"
    (object_dir / "record_trigger").mkdir(parents=True, exist_ok=True)
    (object_dir / "function").mkdir(parents=True, exist_ok=True)
    
    schemas_dir = target_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    
    platform_dir = target_path / "valstorm_platform"
    platform_dir.mkdir(exist_ok=True)
    
    # Create __init__.py to make it a module
    with open(platform_dir / "__init__.py", "w") as f:
        f.write("# Valstorm Platform SDK\n")
    
    # 3. Copy Platform Assets (Stubs & Docs) for IDE and AI support
    update_local_stubs(target_path)

    # 4. Create a README
    with open(target_path / "README.md", "w") as f:
        f.write(f"# Valstorm Project: {target_path.name}\n\nLocal development environment for Valstorm triggers, functions, and schemas.\n\n## Setup\n\n1. Install dependencies: `uv sync`\n2. Authenticate: `valstorm login`\n3. Pull assets: `valstorm pull` (objects + schemas)\n\nAfter step 1 the MCP server is launchable by AI assistants — no extra step needed.\n\n## AI Assistants\n\nThis project is pre-configured for:\n- **Claude Code** — `.mcp.json` registers the `valstorm` MCP server at the project root. `.claude/settings.json` ships a read-only permissions allowlist so common tools don't prompt on first use. See `CLAUDE.md`.\n- **Claude Desktop** — point it at `uv run run_mcp.py` from this directory.\n- **Gemini CLI** — `.gemini/settings.json` registers the same server. See `GEMINI.md`.\n")

    # 4.1 Create GEMINI.md for AI context
    with open(target_path / "GEMINI.md", "w") as f:
        f.write(f"""# Valstorm AI Context: {target_path.name}

This project contains Valstorm platform development assets.
Platform documentation (permissions, query engine, AI agents) lives in `valstorm_platform/docs/`.

## Setup (do this first)

```bash
uv sync         # install deps into the project's .venv
valstorm login  # authenticate (browser-based)
valstorm pull   # pull existing objects/schema
```

After `uv sync` the `valstorm` MCP server is launchable by Gemini CLI via
`.gemini/settings.json`. If the tools don't appear, run `gemini mcp list`
from this directory to inspect the server's launch status.

## Project Structure
- `object/`: Local copies of record triggers and functions.
- `schemas/`: Local copies of object schemas.
- `valstorm_platform/`: Platform SDK stubs and documentation.
- `valstorm_platform/docs/`: Comprehensive documentation for Valstorm.

## Environment
- **Env**: `{auth.env}`
- **Profile**: `{auth.profile}`
- **Auth tokens**: `~/.valstorm/auth_{auth.env}_{auth.profile}.json` (shared with CLI)
""")


    # 5. Create a .gitignore
    with open(target_path / ".gitignore", "w") as f:
        f.write(".venv/\n__pycache__/\n*.pyc\n.env\nobject/**/*.json\n")

    # 6/7. Bootstrap Claude + Gemini AI assistant configs (idempotent — same helper
    # is reused by `valstorm update-stubs` to refresh existing projects).
    _write_ai_configs(target_path, env=auth.env, profile=auth.profile)

    # 8. Create CLAUDE.md for AI context
    with open(target_path / "CLAUDE.md", "w") as f:
        f.write(f"""# Valstorm Project: {target_path.name}

This is a local Valstorm SDK project for developing record triggers, functions, and schemas.
Platform documentation is in `valstorm_platform/docs/`.

## Setup (do this first)

```bash
# 1. Install dependencies into a project-local .venv
uv sync

# 2. Authenticate (opens a browser)
valstorm login

# 3. Pull existing objects/schema from your org
valstorm pull
```

After `uv sync`, Claude Code and Gemini CLI will be able to launch the
Valstorm MCP server. Start a session in this directory and the `valstorm`
MCP tools (e.g. `run_sql_query`, `get_me`) will appear.

## Commands

```bash
# Pull remote objects/schema to local filesystem
valstorm pull
valstorm pull-schemas

# Push local changes to Valstorm cloud
valstorm push

# Run the MCP server manually (e.g. for Claude Desktop or debugging)
uv run run_mcp.py
```

## Project Structure

- `object/<ObjectName>/record_trigger/` — Python record trigger scripts
- `object/<ObjectName>/function/` — Python function scripts
- `schemas/` — Local copies of object schema definitions (JSON)
- `valstorm_platform/` — Platform SDK stubs for IDE type hints and AI context
- `valstorm_platform/docs/` — Comprehensive Valstorm platform documentation
- `valstorm.json` — Project config (env, profile)
- `run_mcp.py` — MCP server entry point

## Writing Record Triggers

Record triggers are Python scripts placed in `object/<ObjectName>/record_trigger/`.
Import context from `valstorm_platform`:

```python
from valstorm_platform.trigger_context import TriggerContext

def handler(context: TriggerContext):
    record = context.record       # The record that triggered this
    old_record = context.old      # Previous state (for update triggers)
    db = context.db               # DB helper for querying related records
    return record
```

## Writing Functions

Functions are Python scripts placed in `object/<ObjectName>/function/`.

```python
from valstorm_platform.platform_context import PlatformContext

def handler(context: PlatformContext):
    payload = context.payload     # Input payload dict
    db = context.db               # DB helper
    return {{"result": "ok"}}
```

## MCP Tools Available

The `valstorm` MCP server (via `run_mcp.py`) exposes these tools:

**Auth**: `get_me`, `login`, `verify_2fa`, `refresh_auth`, `logout`, `switch_account`, `list_accounts`, `get_environment`

**Records**: `create_records`, `update_records`, `delete_records`

**Schemas**: `list_schemas`, `get_schema`, `create_schema`, `update_schema`, `delete_schema`, `create_field`, `update_field`, `delete_field`

**Query**: `run_sql_query` — SQL-like queries with `ME`, `PHONE:`, and dynamic date keywords

**Scaffolding**: `scaffold_valstorm_object` — creates a full object (schema + fields + permissions) in one call

**OAuth**: `oauth_authorize`, `oauth_get_code`, `oauth_get_token`, `oauth_login_server`

## SQL Query Syntax

```sql
SELECT field1, field2 FROM object_name WHERE condition ORDER BY field LIMIT n
```

Special keywords:
- `ME` — current user (`WHERE owner = ME`)
- `PHONE:` — search all phone fields
- Dynamic dates: `today`, `yesterday`, `this_week`, `last_month`, `this_year`
- Parameterized: `last_n_days:7`, `next_n_months:3`

## Environment

- **Env**: `{auth.env}`
- **Profile**: `{auth.profile}`
- **Config**: `valstorm.json`
- **Auth tokens**: `~/.valstorm/auth_{auth.env}_{auth.profile}.json`

## Troubleshooting

**MCP tools don't appear in Claude Code.**
On first launch in this directory Claude Code will prompt you to approve the
project-scoped MCP server defined in `.mcp.json`. Approve it, then run
`/mcp` to confirm the `valstorm` server is connected. If it shows as failed,
run `claude mcp list` in this directory for the launch error.

**"ModuleNotFoundError: valstorm_mcp" when the MCP starts.**
Run `uv sync` — the project venv was never created or is out of date. The
MCP config in `.mcp.json` sets `VIRTUAL_ENV=""` so uv uses *this* project's
venv, not whatever venv your shell happens to have active.

**Auth tokens expired.**
Run `valstorm login` — both the CLI and the MCP server read tokens from
`~/.valstorm/auth_{auth.env}_{auth.profile}.json`, so a single login covers both.
""")
    console.print("[green]✓[/green] CLAUDE.md created.")

    console.print(f"\n[bold green]🚀 Project initialized successfully in {target_path.absolute()}[/bold green]")
    console.print(
        f"Next steps:\n"
        f"  1. [cyan]cd {target_path.name}[/cyan]\n"
        f"  2. [cyan]uv sync[/cyan]                            [dim](installs the project venv — required before MCP can launch)[/dim]\n"
        f"  3. [cyan]valstorm login[/cyan]                     [dim](opens a browser)[/dim]\n"
        f"  4. [cyan]valstorm pull && valstorm pull-schemas[/cyan]\n"
        f"  5. Start Claude Code or Gemini CLI in this directory — the [bold]valstorm[/bold] MCP server is pre-wired."
    )

@app.command(name="version")
def version():
    """
    Display the Valstorm CLI version from the package metadata.
    """
    data = open(Path(__file__).parent.parent.parent / "pyproject.toml", "r").read()
    version_line = next((line for line in data.splitlines() if line.strip().startswith("version =")), None)
    version = version_line.split("=")[1].strip().strip('"') if version_line else "Unknown"
    console.print(f"Valstorm CLI version: [bold cyan]{version}[/bold cyan]")

@mcp_app.command(name="start")
def mcp_start():
    """
    Start the Valstorm MCP server.
    """
    try:
        from valstorm_mcp.main import mcp as server
        console.print("[bold green]Starting Valstorm MCP server...[/bold green]")
        server.run()
    except ImportError:
        console.print("[bold red]Error:[/bold red] valstorm-mcp package not found. Is it installed?")
        raise typer.Exit(1)

@app.callback()
def main():
    """
    Valstorm Developer CLI.
    """
    pass

deploy_app = typer.Typer(help="Manage deployments.")
deploy_app_group = typer.Typer(help="Manage App deployments.")
deploy_app.add_typer(deploy_app_group, name="app")
app.add_typer(deploy_app, name="deploy")

def get_app_id_by_name(auth, api_base_url, app_name: str) -> str:
    """Helper to lookup an app ID by its name."""
    response = httpx.get(
        f"{api_base_url}/app",
        headers={"Authorization": f"Bearer {auth.access_token}"},
        timeout=10.0
    )
    if response.status_code != 200:
        console.print(f"[bold red]Failed to fetch apps:[/bold red] {response.text}")
        raise typer.Exit(1)
        
    apps = response.json()
    # Handle both list and paginated dict response formats
    apps_list = apps if isinstance(apps, list) else apps.get("items", apps.get("data", []))
    if not isinstance(apps_list, list):
        # Fallback if the response shape is unusual
        if isinstance(apps, dict) and "records" in apps:
            apps_list = apps["records"]
        else:
            apps_list = []
            
    for a in apps_list:
        if isinstance(a, dict) and a.get("name") == app_name:
            return a.get("id")
            
    console.print(f"[bold red]App not found:[/bold red] {app_name}")
    raise typer.Exit(1)


@deploy_app_group.command(name="sandbox")
def push_sandbox_app(
    sandbox_name: str = typer.Argument(..., help="The name of the sandbox environment."),
    app_name: str = typer.Argument(..., help="The name of the application being pushed."),
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Optional target destination for the deployment (e.g., 'production', 'staging')."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Push a sandbox app deployment to a specified target environment.
    """
    auth = get_auth(profile=profile, env=env, use_parent=True)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    api_base_url = get_api_base_url(env=env)
    
    try:
        # Execute POST Push
        url = f"{api_base_url}/sandbox/{sandbox_name}/app/{app_name}/push"
        params = {}
        if target:
            params["target"] = target
            console.print(f"Pushing app [blue]{app_name}[/blue] from sandbox [blue]{sandbox_name}[/blue] to target [green]{target}[/green]...")
        else:
            console.print(f"Pushing app [blue]{app_name}[/blue] from sandbox [blue]{sandbox_name}[/blue] to parent environment...")
            
        response = httpx.post(
            url, 
            params=params, 
            headers={"Authorization": f"Bearer {auth.access_token}"},
            timeout=120.0
        )
        if response.status_code == 200:
            console.print("[bold green]✓ Sandbox push successful![/bold green]")
            
            try:
                data = response.json()
                from rich.json import JSON
                console.print(JSON.from_data(data))
            except Exception:
                console.print(response.text)
        else:
            console.print(f"[bold red]Push failed ({response.status_code}):[/bold red]")
            try:
                err_data = response.json()
                console.print(f"[red]{json.dumps(err_data, indent=2)}[/red]")
            except Exception:
                console.print(f"[red]{response.text}[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[bold red]Error connecting to API:[/bold red] {str(e)}")
        raise typer.Exit(1)


@deploy_app_group.command(name="marketplace")
def deploy_marketplace(
    app_name: str = typer.Argument(..., help="The name of the application being deployed."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Deploy the current app state to the Marketplace (Base database).
    """
    auth = get_auth(profile=profile, env=env, use_parent=True)
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    api_base_url = get_api_base_url(env=env)
    
    url = f"{api_base_url}/apps/marketplace-deployment?id={app_name}"
    console.print(f"Deploying app [blue]{app_name}[/blue] to Marketplace...")
    
    response = httpx.post(
        url,
        json={},
        headers={"Authorization": f"Bearer {auth.access_token}"},
        timeout=120.0
    )
    if response.status_code == 200:
        console.print("[bold green]✓ Marketplace deployment successful![/bold green]")
        try:
            from rich.json import JSON
            console.print(JSON.from_data(response.json()))
        except Exception:
            console.print(response.text)
    else:
        console.print(f"[bold red]Deployment failed ({response.status_code}):[/bold red] {response.text}")
        raise typer.Exit(1)

@deploy_app_group.command(name="next-env")
def deploy_next_env(
    app_name: str = typer.Argument(..., help="The name of the application being deployed."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Deploy the app to the next environment.
    """
    auth = get_auth(profile=profile, env=env, use_parent=True)
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    api_base_url = get_api_base_url(env=env)
    
    url = f"{api_base_url}/apps/deploy/{app_name}"
    console.print(f"Deploying app [blue]{app_name}[/blue] to next environment...")
    
    response = httpx.get(
        url,
        headers={"Authorization": f"Bearer {auth.access_token}"},
        timeout=120.0
    )
    if response.status_code == 200:
        console.print("[bold green]✓ Next environment deployment successful![/bold green]")
        try:
            from rich.json import JSON
            console.print(JSON.from_data(response.json()))
        except Exception:
            console.print(response.text)
    else:
        console.print(f"[bold red]Deployment failed ({response.status_code}):[/bold red] {response.text}")
        raise typer.Exit(1)

@deploy_app_group.command(name="apply-subscribers")
def apply_subscribers(
    app_name: str = typer.Argument(..., help="The name of the application being applied."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Apply app updates to all subscribers.
    """
    auth = get_auth(profile=profile, env=env, use_parent=True)
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    api_base_url = get_api_base_url(env=env)
    
    url = f"{api_base_url}/apps/app-update-subscribers?id={app_name}"
    console.print(f"Applying updates for app [blue]{app_name}[/blue] to subscribers...")
    
    response = httpx.post(
        url,
        json={},
        headers={"Authorization": f"Bearer {auth.access_token}"},
        timeout=120.0
    )
    if response.status_code == 200:
        console.print("[bold green]✓ Updates applied to subscribers![/bold green]")
        try:
            from rich.json import JSON
            console.print(JSON.from_data(response.json()))
        except Exception:
            console.print(response.text)
    else:
        console.print(f"[bold red]Failed to apply updates ({response.status_code}):[/bold red] {response.text}")
        raise typer.Exit(1)

@manifest_app.command(name="generate")
def generate_manifest(name: str = typer.Argument(..., help="The name of the manifest file to generate")):
    """
    Generate a boilerplate deployment manifest.
    """
    if not name.endswith(".json"):
        name += ".json"
        
    try:
        root = get_project_root()
    except Exception:
        console.print("[bold red]Error:[/bold red] Must be run inside a Valstorm project.")
        raise typer.Exit(1)
        
    manifests_dir = root / "manifests"
    manifests_dir.mkdir(exist_ok=True)
    
    file_path = manifests_dir / name
    if file_path.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest {file_path.name} already exists.")
        raise typer.Exit(1)
        
    boilerplate = {
        "version": "1.0",
        "description": "Deployment manifest",
        "objects": {}
    }
    
    with open(file_path, "w") as f:
        json.dump(boilerplate, f, indent=4)
        
    console.print(f"[bold green]✓ Generated manifest:[/bold green] {file_path}")


