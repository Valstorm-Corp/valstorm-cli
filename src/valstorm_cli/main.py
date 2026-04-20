import typer
import httpx
from rich.console import Console
import getpass
import os
import json
import shutil
import subprocess
import sys
from pathlib import Path
from .auth import ValstormAuth, get_api_base_url

app = typer.Typer(help="Valstorm Developer CLI", no_args_is_help=True)
mcp_app = typer.Typer(help="Manage the Valstorm MCP Server")
auth_app = typer.Typer(help="Manage Valstorm authentication profiles")

app.add_typer(mcp_app, name="mcp")
app.add_typer(auth_app, name="auth")
console = Console()

@auth_app.command(name="list")
def list_profiles():
    """
    List all available saved environments and profiles you can log into.
    """
    auth_dir = Path.home() / ".valstorm"
    if not auth_dir.exists():
        console.print("[yellow]No Valstorm profiles found. Please login first.[/yellow]")
        return
        
    found = []
    # auth files are usually named auth_{env}_{profile}.json or auth_{env}.json
    for path in auth_dir.glob("auth_*.json"):
        name_parts = path.stem.split("_")
        env = "prod"
        profile = "default"
        
        if len(name_parts) == 2:
            # auth_{env}.json
            env = name_parts[1]
        elif len(name_parts) >= 3:
            # auth_{env}_{profile}.json
            env = name_parts[1]
            profile = "_".join(name_parts[2:])
            
        try:
            with open(path, "r") as f:
                data = json.load(f)
            user = data.get("user", {})
            org_name = data.get("organization_name", "Unknown Org")
            found.append({"env": env, "profile": profile, "org": org_name, "user": user.get("name", "Unknown User"), "email": user.get("email", "Unknown Email"), "org_id": user.get("organization_id", "Unknown Org ID"), "user_id": user.get("id", "Unknown User ID")})
        except Exception:
            found.append({"env": env, "profile": profile, "org": "Invalid file"})

    if not found:
        console.print("[yellow]No Valstorm profiles found. Please login first.[/yellow]")
        return

    console.print("\n[bold]Available Authentication Profiles:[/bold]")
    
    # Identify currently active profile if in a project
    active_profile = None
    active_env = None
    try:
        current = Path.cwd()
        while current != current.parent:
            if (current / "valstorm.json").exists():
                with open(current / "valstorm.json", "r") as f:
                    config = json.load(f)
                    active_profile = config.get("profile")
                    active_env = config.get("env")
                break
            current = current.parent
    except Exception:
        pass

    for entry in found:
        is_active = (entry["profile"] == active_profile and entry["env"] == active_env)
        marker = "[green]*[/green]" if is_active else " "
        console.print(f"{marker} Profile: [cyan]{entry['profile']}[/cyan] | Env: [blue]{entry['env']}[/blue] | Org: {entry['org']}")
        
    if active_profile:
        console.print(f"\n[dim]* Indicates currently targeted profile in valstorm.json[/dim]")

@auth_app.command(name="switch")
def switch_profile(
    profile: str = typer.Argument(..., help="The profile to switch to."),
    env: str = typer.Option(None, "--env", "-e", help="The environment to switch to.")
):
    """
    Switch the currently targeted auth profile for the current Valstorm project.
    """
    try:
        root = get_project_root()
    except Exception:
        console.print("[bold red]Cannot switch profiles: Not in a Valstorm project directory.[/bold red]")
        raise typer.Exit(1)
        
    config = load_config(root)
    
    # Fallback to existing env if not provided
    new_env = env or config.get("env") or "prod"
    
    # Check if this profile actually exists
    auth_dir = Path.home() / ".valstorm"
    auth_file = auth_dir / f"auth_{new_env}_{profile}.json"
    legacy_auth_file = auth_dir / f"auth_{new_env}.json"
    
    if not auth_file.exists() and not (profile == "default" and legacy_auth_file.exists()):
        console.print(f"[yellow]Warning:[/yellow] Profile [cyan]{profile}[/cyan] for environment [blue]{new_env}[/blue] does not appear to have saved credentials.")
        console.print(f"You may need to run: [bold]valstorm login -p {profile} -e {new_env}[/bold]")
        if not typer.confirm("Do you want to switch to it anyway?"):
            raise typer.Exit(0)
            
    config["profile"] = profile
    config["env"] = new_env
    
    with open(root / "valstorm.json", "w") as f:
        json.dump(config, f, indent=4)
        
    # Also update Gemini MCP Settings if they exist
    gemini_dir = root / ".gemini"
    settings_file = gemini_dir / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, "r") as f:
                gemini_settings = json.load(f)
                
            if "mcpServers" not in gemini_settings:
                gemini_settings["mcpServers"] = {}
            if "valstorm" not in gemini_settings["mcpServers"]:
                gemini_settings["mcpServers"]["valstorm"] = {}
            if "env" not in gemini_settings["mcpServers"]["valstorm"]:
                gemini_settings["mcpServers"]["valstorm"]["env"] = {}
                
            gemini_settings["mcpServers"]["valstorm"]["env"]["VALSTORM_PROFILE"] = profile
            gemini_settings["mcpServers"]["valstorm"]["env"]["VALSTORM_ENV"] = new_env
            
            with open(settings_file, "w") as f:
                json.dump(gemini_settings, f, indent=4)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not update Gemini MCP settings: {e}[/yellow]")
            
    console.print(f"[green]✓[/green] Successfully switched project target to Profile: [cyan]{profile}[/cyan] (Env: [blue]{new_env}[/blue])")

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
            console.print(f"[bold green]SUCCESS:[/bold green] API is running and responded with HTTP 200.")
            console.print(response.json())
        else:
            console.print(f"[bold yellow]WARNING:[/bold yellow] API responded with status code {response.status_code}")
            console.print(response.text)
            
    except httpx.RequestError as e:
        console.print(f"[bold red]ERROR:[/bold red] Could not connect to the API. {e}")
    except Exception as e:
        console.print(f"[bold red]UNEXPECTED ERROR:[/bold red] {e}")

@app.command()
def login(
    profile: str = typer.Option("default", "--profile", "-p", help="Profile name to save these credentials under."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment (local, dev, prod).")
):
    """
    Authenticate with Valstorm.
    """
    auth = ValstormAuth(profile=profile, env=env)
    
    console.print(f"Logging in to [blue]{get_api_base_url(auth.env)}[/blue] (Profile: [cyan]{auth.profile}[/cyan])")
    
    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)

    with httpx.Client(base_url=get_api_base_url(auth.env)) as client:
        # OAuth2 password flow uses form-urlencoded data
        response = client.post("/oauth2/login", data={
            "grant_type": "password",
            "username": email,
            "password": password
        })

        if response.status_code != 200:
            console.print(f"[bold red]Login Failed:[/bold red] {response.status_code}")
            console.print(response.text)
            raise typer.Exit(1)

        data = response.json()

        # Handle 2FA if required
        if "detail" in data and "2FA" in data["detail"]:
            console.print(f"[yellow]{data['detail']}[/yellow]")
            code = typer.prompt("Enter 2FA Code")
            
            verify_response = client.post("/oauth2/verify-2fa", json={
                "email": email,
                "code": code
            })
            
            if verify_response.status_code != 200:
                console.print(f"[bold red]2FA Verification Failed:[/bold red] {verify_response.text}")
                raise typer.Exit(1)
                
            data = verify_response.json()

        if "access_token" in data:
            auth.save_tokens(
                access_token=data["access_token"], 
                refresh_token=data.get("refresh_token")
            )
            
            # Fetch user details to save organization name for the profile list
            with auth.get_client() as auth_client:
                load_res = auth_client.get("/auth/load")
                if load_res.status_code == 200:
                    user_data = load_res.json()
                    user = user_data.get("user", user_data) # handle both nested and unnested responses
                    if user.get("organization_name"):
                        auth.save_tokens(
                            access_token=data["access_token"],
                            refresh_token=data.get("refresh_token"),
                            organization_name=user.get("organization_name")
                        )
                        
            console.print("[bold green]Successfully logged in![/bold green]")
        else:
            console.print("[bold red]Unexpected response during login.[/bold red]")
            console.print(data)

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
def whoami(
    profile: str = typer.Option("default", "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    Display current authenticated user info.
    """
    auth = ValstormAuth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        response = client.get("/auth/load")
        if response.status_code == 200:
            data = response.json()
            user = data.get("user", {})
            console.print(f"Logged in as: [bold cyan]{user.get('name', 'Unknown')}[/bold cyan]")
            console.print(f"Organization: [bold green]{user.get('organization_name', 'Unknown')}[/bold green]")
            console.print(f"Email: {user.get('email', 'Unknown')}")
            console.print(f"User ID: {user.get('id', 'Unknown')}")
            console.print(f"Org Id: {user.get('organization_id', 'Unknown')}")
            console.print(f"Role: {user.get('role', {}).get('name', 'Unknown')}")
        else:
            console.print(f"[bold red]Failed to load user data:[/bold red] {response.status_code}")

@app.command()
def init(
    path: str = typer.Argument(None, help="Name of the directory to initialize the project in."),
    profile: str = typer.Option("default", "--profile", "-p", help="The auth profile to use."),
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
    auth = ValstormAuth(profile=profile, env=env)
    
    config = {
        "env": auth.env,
        "profile": auth.profile
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
        f.write(f"# Valstorm Project: {target_path.name}\n\nLocal development environment for Valstorm triggers, functions, and schemas.\n\n## Setup\n\n1. Install dependencies: `uv sync`\n2. Run MCP: `uv run run_mcp.py` or use Gemini CLI.\n3. Pull assets: `valstorm pull` and `valstorm pull-schemas`\n")

    # 4.1 Create GEMINI.md for AI context
    with open(target_path / "GEMINI.md", "w") as f:
        f.write(f"""# Valstorm AI Context: {target_path.name}

This project contains Valstorm platform development assets. 
Documentation for the platform, including permissions, query engine, and AI agents, can be found in the `valstorm_platform/docs` directory.

## Project Structure
- `object/`: Local copies of record triggers and functions.
- `schemas/`: Local copies of object schemas.
- `valstorm_platform/`: Platform SDK stubs and documentation.
- `valstorm_platform/docs/`: Comprehensive documentation for Valstorm.
""")


    # 5. Create a .gitignore
    with open(target_path / ".gitignore", "w") as f:
        f.write(".venv/\n__pycache__/\n*.pyc\n.env\nobject/**/*.json\n")

    # 6. Bootstrap Gemini Settings
    gemini_dir = target_path / ".gemini"
    gemini_dir.mkdir(exist_ok=True)
    gemini_settings = {
        "mcpServers": {
            "valstorm": {
                "command": "uv",
                "args": ["run", "run_mcp.py"],
                "env": {
                    "VALSTORM_ENV": auth.env,
                    "VALSTORM_PROFILE": auth.profile
                }
            }
        },
        "hooks": {
            "SessionStart": [
                {
                    "matcher": ".*",
                    "hooks": [
                        {
                            "name": "inject-docs",
                            "type": "command",
                            "command": "python3 valstorm_platform/hooks/inject_docs.py"
                        }
                    ]
                }
            ]
        }
    }
    with open(gemini_dir / "settings.json", "w") as f:
        json.dump(gemini_settings, f, indent=4)
    console.print("[green]✓[/green] Gemini MCP settings bootstrapped.")

    console.print(f"\n[bold green]🚀 Project initialized successfully in {target_path.absolute()}[/bold green]")
    console.print(f"Next steps:\n  1. [cyan]cd {target_path.name}[/cyan]\n  2. [cyan]uv sync[/cyan]\n  3. [cyan]valstorm pull && valstorm pull-schemas[/cyan]")
def get_project_root() -> Path:
    """Helper to find the valstorm.json file by searching upwards."""
    current = Path.cwd()
    while current != current.parent:
        if (current / "valstorm.json").exists():
            return current
        current = current.parent
    console.print("[bold red]Error:[/bold red] Could not find 'valstorm.json'. Are you in a Valstorm project directory?")
    raise typer.Exit(1)

def load_config(root: Path) -> dict:
    with open(root / "valstorm.json", "r") as f:
        return json.load(f)

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

@app.command(name="update-stubs")
def update_stubs_command():
    """
    Update the local PlatformContext stubs to the version bundled with the CLI.
    """
    root = get_project_root()
    update_local_stubs(root)

@app.command()
def pull(
    object_type: str = typer.Argument(None, help="Specific object type to pull (e.g., record_trigger)."),
    force: bool = typer.Option(False, "--force", "--yes", "-y", help="Overwrite local changes without asking."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Download records for metadata objects from the Valstorm cloud.
    """
    root = get_project_root()
    
    # Auto-update stubs silently on pull
    update_local_stubs(root, silent=True)
    
    config = load_config(root)
    
    auth_profile = profile or config.get("profile")
    auth_env = env or config.get("env")
    
    auth = ValstormAuth(profile=auth_profile, env=auth_env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    # 1. Fetch available schemas to see what we can pull
    with auth.get_client() as client:
        schema_res = client.get("/schemas")
        if schema_res.status_code != 200:
            console.print("[bold red]Failed to fetch schemas.[/bold red]")
            raise typer.Exit(1)
        available_schemas = schema_res.json()

    # 2. Define target types
    if object_type:
        if object_type not in available_schemas:
            console.print(f"[bold red]Error:[/bold red] Object type '{object_type}' not found in schemas.")
            raise typer.Exit(1)
        target_types = [object_type]
    else:
        core_types = ["record_trigger", "function"]
        metadata_types = [
            "ai_agent", "app", "app_page", "app_metadata", 
            "permission", "notification_setting", 
            "schedule_trigger_setting", "workspace"
        ]
        # Filter types that exist in the schemas
        target_types = [t for t in (core_types + metadata_types) if t in available_schemas]
    
    if not target_types:
        console.print("[yellow]No matching objects found in schemas to pull records for.[/yellow]")
    
    for file_type in target_types:
        console.print(f"Pulling [cyan]{file_type}[/cyan]s from [blue]{get_api_base_url(auth.env)}[/blue]...")
        query = f"SELECT * FROM {file_type}"
        
        with auth.get_client() as client:
            response = client.post("/query", json={"query": query})
            
            if response.status_code != 200:
                console.print(f"[bold red]Fetch failed for {file_type}:[/bold red] {response.status_code}")
                continue
                
            data = response.json()
            records = data.get("data", data) if isinstance(data, dict) else data
            
            if not isinstance(records, list):
                console.print(f"[yellow]No records found for {file_type}.[/yellow]")
                continue

            target_dir = root / "object" / file_type
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Save metadata alongside the code
            with open(target_dir / f"{file_type}_metadata.json", "w") as f:
                json.dump(records, f, indent=4)

            # Extract code if present
            count = 0
            code_count = 0
            for record in records:
                count += 1
                file_name = record.get("file_name")
                code = record.get("code")
                
                if file_name and code:
                    file_path = target_dir / file_name
                    
                    # Check if local file exists and has different content
                    if file_path.exists() and not force:
                        with open(file_path, "r") as f:
                            local_code = f.read()
                        if local_code != code:
                            choice = typer.prompt(
                                f"Local changes detected in {file_name}. Overwrite? [y/N/a] (a=all)",
                                default="n"
                            ).lower()
                            
                            if choice == 'a':
                                force = True
                            elif choice != 'y':
                                console.print(f"Skipping {file_name}")
                                continue
                    
                    with open(file_path, "w") as f:
                        f.write(code)
                    code_count += 1
            
            if code_count > 0:
                console.print(f"[green]✓[/green] Synchronized {count} {file_type} records ({code_count} files).")
            else:
                console.print(f"[green]✓[/green] Synchronized {count} {file_type} records.")
    
    # Also pull schema definitions
    try:
        pull_schemas(object_type=object_type, profile=profile, env=env)
    except Exception as e:
        console.print(f"[yellow]![/yellow] Warning: Failed to pull schemas during pull: {e}")

@app.command(name="pull-schemas")
def pull_schemas(
    object_type: str = typer.Argument(None, help="Specific object schema to pull."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Download object schemas from the Valstorm cloud.
    """
    root = get_project_root()
    config = load_config(root)
    
    auth_profile = profile or config.get("profile")
    auth_env = env or config.get("env")
    
    auth = ValstormAuth(profile=auth_profile, env=auth_env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    console.print(f"Pulling [cyan]schemas[/cyan] from [blue]{get_api_base_url(auth.env)}[/blue]...")
    
    with auth.get_client() as client:
        # If specific object requested, use the specific endpoint if it's more efficient, 
        # but the current logic fetches all and filters. 
        # Actually /schemas returns everything, let's keep it simple for now or check if /schema/{object} is better.
        endpoint = f"/schema/{object_type}" if object_type else "/schemas"
        response = client.get(endpoint)
        
        if response.status_code != 200:
            console.print(f"[bold red]Fetch failed for schemas:[/bold red] {response.status_code}")
            raise typer.Exit(1)
            
        data = response.json()
        
        if object_type:
            # Response is a single schema object
            schemas = {object_type: data}
        else:
            # Response is a map of schemas
            schemas = data
        
        if not isinstance(schemas, dict):
            console.print("[bold red]Unexpected response format for schemas.[/bold red]")
            raise typer.Exit(1)

        target_dir = root / "schemas"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        count = 0
        for api_name, schema_data in schemas.items():
            file_path = target_dir / f"{api_name}.json"
            with open(file_path, "w") as f:
                json.dump(schema_data, f, indent=4)
            count += 1
            
        console.print(f"[green]✓[/green] Synchronized {count} schema files to {target_dir}")

@app.command()
def push(
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Upload local changes to the Valstorm cloud.
    """
    root = get_project_root()
    config = load_config(root)
    
    auth_profile = profile or config.get("profile")
    auth_env = env or config.get("env")
    
    auth = ValstormAuth(profile=auth_profile, env=auth_env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    object_root = root / "object"
    if not object_root.exists():
        console.print("[yellow]No 'object' directory found. Nothing to push.[/yellow]")
        return

    # Identify which types we have locally
    types = [d.name for d in object_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
    
    if not types:
        console.print("[yellow]No object types found in 'object' directory.[/yellow]")
        return

    for file_type in types:
        local_dir = object_root / file_type
        metadata_path = local_dir / f"{file_type}_metadata.json"
        
        metadata = []
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
        updates_payload = []
        creates_payload = []
        
        # Map current metadata for easy lookup
        meta_map = {r.get("file_name"): r for r in metadata if r.get("file_name")}
        
        # Scan local directory for changes and new files
        for file_path in local_dir.glob("*.py"):
            file_name = file_path.name
            with open(file_path, "r") as f:
                local_code = f.read()
            
            if file_name in meta_map:
                # This is an existing file, check for updates
                record = meta_map[file_name]
                if local_code != record.get("code"):
                    updates_payload.append({
                        "id": record["id"],
                        "code": local_code,
                        "app": record.get("app")
                    })
            else:
                # This is a NEW file, we need to create it in the cloud
                console.print(f"Detected new local {file_type}: [cyan]{file_name}[/cyan]")
                if typer.confirm(f"Do you want to create {file_name} in the cloud?"):
                    name = typer.prompt(f"Display name for this {file_type}", default=file_name.replace(".py", "").replace("_", " ").title())
                    app_id = typer.prompt("App ID (The UUID of the Valstorm App this belongs to)")
                    
                    new_record = {
                        "name": name,
                        "file_name": file_name,
                        "code": local_code,
                        "app": app_id,
                        "active": True
                    }
                    
                    if file_type == "record_trigger":
                        new_record["object_api_name"] = typer.prompt("Object API Name (e.g., contact, lead)")
                        new_record["trigger_type"] = typer.prompt("Trigger Type (before_upsert, after_upsert, etc)", default="after_upsert")
                    
                    creates_payload.append(new_record)
        
        # 1. Handle Creates
        if creates_payload:
            console.print(f"Creating {len(creates_payload)} new [cyan]{file_type}[/cyan]s on [blue]{get_api_base_url(auth.env)}[/blue]...")
            with auth.get_client() as client:
                response = client.post(f"/object/{file_type}", json=creates_payload)
                if response.status_code in [200, 201]:
                    console.print(f"[bold green]✓ Successfully created {file_type} records.[/bold green]")
                    newly_created = response.json() if isinstance(response.json(), list) else [response.json()]
                    metadata.extend(newly_created)
                else:
                    console.print(f"[bold red]Create failed for {file_type}:[/bold red] {response.status_code}")
                    console.print(response.text)

        # 2. Handle Updates
        if updates_payload:
            console.print(f"Pushing {len(updates_payload)} updates for [cyan]{file_type}[/cyan] to [blue]{get_api_base_url(auth.env)}[/blue]...")
            with auth.get_client() as client:
                response = client.patch(f"/object/{file_type}", json=updates_payload)
                if response.status_code in [200, 204]:
                    console.print(f"[bold green]✓ Successfully updated {file_type} records.[/bold green]")
                    updated_records = response.json() if response.status_code == 200 else []
                    if updated_records:
                        # Refresh metadata map for updating
                        current_meta_map = {r["id"]: r for r in metadata}
                        for updated in updated_records:
                            current_meta_map[updated["id"]] = updated
                        metadata = list(current_meta_map.values())
                else:
                    console.print(f"[bold red]Push failed for {file_type}:[/bold red] {response.status_code}")
                    console.print(response.text)
        
        # Save updated metadata back to disk
        if creates_payload or updates_payload:
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=4)
        
        if not (creates_payload or updates_payload):
            console.print(f"No changes detected for [cyan]{file_type}[/cyan]s.")

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

if __name__ == "__main__":
    app()
