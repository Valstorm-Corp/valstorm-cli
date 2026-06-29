import typer
import httpx
import getpass
import os
import json
import csv
import shutil
import subprocess
import sys
import webbrowser
import secrets
import hashlib
import base64
import threading
import time
from typing import Optional, Annotated
from pathlib import Path
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from .auth import ValstormAuth, get_api_base_url, get_base_url, get_web_url
from .scaffold import run_web_scaffolding, prepare_web_push
from rich.console import Console


app = typer.Typer(help="Valstorm Developer CLI", no_args_is_help=True)
mcp_app = typer.Typer(help="Manage the Valstorm MCP Server")
auth_app = typer.Typer(help="Manage Valstorm authentication profiles")
manifest_app = typer.Typer(help="Manage Valstorm manifests")

app.add_typer(mcp_app, name="mcp")
app.add_typer(auth_app, name="auth")
app.add_typer(manifest_app, name="manifest")
from .sandbox import sandbox_app
from .record import record_app
from .schema import schema_app
from .field import field_app
from .query import sql, graphql

app.add_typer(sandbox_app, name="sandbox")
app.add_typer(record_app, name="record")
app.add_typer(schema_app, name="schema")
app.add_typer(field_app, name="field")
app.command(name="sql")(sql)
app.command(name="graphql")(graphql)
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
            content = path.read_text().strip()
            if not content:
                found.append({"env": env, "profile": profile, "org": "Empty file (Not logged in)"})
                continue
            data = json.loads(content)
            user = data.get("user", {})
            org_name = data.get("organization_name", "Unknown Org")
            found.append({"env": env, "profile": profile, "org": org_name, "user": user.get("name", "Unknown User"), "email": user.get("email", "Unknown Email"), "org_id": user.get("organization_id", "Unknown Org ID"), "user_id": user.get("id", "Unknown User ID")})
        except Exception as e:
            found.append({"env": env, "profile": profile, "org": f"Corrupted file ({str(e)})"})

    if not found:
        console.print("[yellow]No Valstorm profiles found. Please login first.[/yellow]")
        return

    console.print("\n[bold]Available Authentication Profiles:[/bold]")
    
    # Identify currently active profile if in a project
    active_profile = None
    active_env = None
    try:
        root = find_project_root()
        if root:
            with open(root / "valstorm.json", "r") as f:
                config = json.load(f)
                active_profile = config.get("profile")
                active_env = config.get("env")
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

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        
        if code:
            self.server.auth_code = code
            self.server.state = state
        
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        
        message = """
        <html>
            <head><title>Authentication Successful</title></head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                <h1 style="color: #4CAF50;">Authentication Successful!</h1>
                <p>You can now close this tab and return to the terminal.</p>
            </body>
        </html>
        """
        self.wfile.write(message.encode("utf-8"))

    def log_message(self, format, *args):
        # Optional: Uncomment to see requests in terminal if still debugging
        # console.print(f"[dim]Local server: {format % args}[/dim]")
        return

def get_pkce_pair():
    verifier = secrets.token_urlsafe(32)
    challenge_hash = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(challenge_hash).decode("utf-8").rstrip("=")
    return verifier, challenge

@app.command()
def login(
    method: Optional[str] = typer.Argument(None, help="Login method, e.g., 'pat'"),
    key: Optional[str] = typer.Argument(None, help="The token/key for the given method"),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name to save these credentials under."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment (local, dev, prod)."),
    use_password: bool = typer.Option(False, "--password", help="Use legacy password flow."),
    pat: str = typer.Option(None, "--pat", help="Login using a Personal Access Token (PAT).")
):
    """
    Authenticate with Valstorm.
    """
    auth = get_auth(profile=profile, env=env)
    
    console.print(f"Logging in to [blue]{get_api_base_url(auth.env)}[/blue] (Profile: [cyan]{auth.profile}[/cyan])")

    if method == "pat" and key:
        pat = key
    elif method == "pat" and not key:
        console.print("[bold red]Error: You must provide a token when using 'pat' method. Usage: valstorm login pat <key>[/bold red]")
        raise typer.Exit(1)
    elif method:
        console.print(f"[bold red]Unknown login method: {method}[/bold red]")
        raise typer.Exit(1)

    if pat:
        auth.save_tokens(access_token=pat, refresh_token="") # empty string wipes the old refresh token
        if auth.ensure_valid_token():
            console.print(f"[bold green]Successfully logged in using PAT for profile '{auth.profile}'.[/bold green]")
            return
        else:
            console.print("[bold red]Invalid Personal Access Token.[/bold red]")
            raise typer.Exit(1)
    
    if use_password:
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
    else:
        # OAuth Browser Flow
        client_id = "valstorm-cli"
        redirect_uri = "http://127.0.0.1:8011/callback"
        port = 8011
        
        verifier, challenge = get_pkce_pair()
        state = secrets.token_urlsafe(16)
        
        with httpx.Client(base_url=get_api_base_url(auth.env)) as client:
            try:
                # 1. Get Authorize URL from API
                auth_res = client.post("/oauth2/authorize", json={
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "state": state,
                    "code_challenge": challenge
                })
                
                if auth_res.status_code != 200:
                    console.print(f"[bold red]Authorization failed:[/bold red] {auth_res.text}")
                    console.print("[yellow]Hint: Ensure you have an Integrated App with client_id 'valstorm-cli' and redirect_uri 'http://127.0.0.1:8011/callback' configured in your organization.[/yellow]")
                    raise typer.Exit(1)
                
                authorize_url = auth_res.json()["redirect_url"]
                
                # 2. Start local server
                server = HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
                server.auth_code = None
                server.state = None
                
                thread = threading.Thread(target=server.serve_forever)
                thread.daemon = True
                thread.start()
                
                console.print(f"Opening browser for authentication...")
                webbrowser.open(authorize_url)
                
                # 3. Wait for code
                while server.auth_code is None:
                    try:
                        time.sleep(0.1)
                    except KeyboardInterrupt:
                        server.shutdown()
                        server.server_close()
                        raise typer.Exit(1)
                
                auth_code = server.auth_code
                received_state = server.state
                
                # Cleanup server immediately
                server.shutdown()
                server.server_close()
                
                console.print("[green]✓ Received authentication code.[/green]")
                
                if received_state != state:
                    console.print("[bold red]Error:[/bold red] State mismatch. Authentication failed.")
                    raise typer.Exit(1)
                
                # 3. Exchange code for tokens
                response = client.post("/oauth2/token", json={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": auth_code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": verifier
                })
                
                if response.status_code != 200:
                    console.print(f"[bold red]Token Exchange Failed:[/bold red] {response.status_code}")
                    console.print(response.text)
                    raise typer.Exit(1)
                
                data = response.json()
            except httpx.RequestError as e:
                console.print(f"[bold red]Connection Error:[/bold red] {e}")
                raise typer.Exit(1)

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

@app.command(name="logout")
def logout(
    profile: str = typer.Option(None, "--profile", "-p", help="Specific profile to remove."),
    env: str = typer.Option(None, "--env", "-e", help="Specific environment to remove."),
    clear_all: bool = typer.Option(False, "--all", help="Remove all saved profiles.")
):
    """
    Log out by removing saved authentication profiles.
    """
    auth_dir = Path.home() / ".valstorm"
    if not auth_dir.exists():
        console.print("[yellow]No Valstorm profiles found.[/yellow]")
        return

    if clear_all:
        count = 0
        for path in auth_dir.glob("auth_*.json"):
            path.unlink()
            count += 1
        console.print(f"[bold green]Successfully removed {count} profile(s).[/bold green]")
        return
        
    # If not clearing all, determine env and profile
    if not env or not profile:
        root = find_project_root()
        if root:
            try:
                config = load_config(root)
                env = env or config.get("env", "prod")
                profile = profile or config.get("profile", "default")
            except Exception:
                env = env or "prod"
                profile = profile or "default"
        else:
            env = env or "prod"
            profile = profile or "default"
            
    auth_file = auth_dir / f"auth_{env}_{profile}.json"
    legacy_auth_file = auth_dir / f"auth_{env}.json"
    
    if auth_file.exists():
        auth_file.unlink()
        console.print(f"[bold green]Successfully removed profile '{profile}' for environment '{env}'.[/bold green]")
    elif profile == "default" and legacy_auth_file.exists():
        legacy_auth_file.unlink()
        console.print(f"[bold green]Successfully removed legacy profile for environment '{env}'.[/bold green]")
    else:
        console.print(f"[yellow]Warning: Profile '{profile}' for environment '{env}' not found.[/yellow]")

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



@app.command(name="open")
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

@app.command()
def whoami(
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    Display current authenticated user info.
    """
    auth = get_auth(profile=profile, env=env)
    
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

def find_project_root() -> Optional[Path]:
    """Helper to find the valstorm.json file by searching upwards."""
    current = Path.cwd()
    while current != current.parent:
        if (current / "valstorm.json").exists():
            return current
        current = current.parent
    return None

def get_project_root() -> Path:
    root = find_project_root()
    if root:
        return root
    console.print("[bold red]Error:[/bold red] Could not find 'valstorm.json'. Are you in a Valstorm project directory?")
    raise typer.Exit(1)

def get_auth(profile: Optional[str] = None, env: Optional[str] = None) -> ValstormAuth:
    """
    Helper to resolve authentication using:
    1. Explicit command line arguments (if provided)
    2. Local project configuration (valstorm.json)
    3. Environment variables (handled by ValstormAuth)
    4. Defaults (handled by ValstormAuth)
    """
    auth_profile = profile
    auth_env = env

    root = find_project_root()
    if root:
        try:
            config = load_config(root)
            if auth_profile is None:
                auth_profile = config.get("profile")
            if auth_env is None:
                auth_env = config.get("env")
        except Exception:
            pass

    return ValstormAuth(profile=auth_profile, env=auth_env)

def load_config(root: Path) -> dict:
    with open(root / "valstorm.json", "r") as f:
        return json.load(f)

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


def _build_mcp_server_config(env: str, profile: str) -> dict:
    """The canonical launch spec for the valstorm MCP server.

    - `--directory .` makes uv resolve the project root explicitly, robust to client cwd quirks.
    - `VIRTUAL_ENV=""` blocks a parent shell's active venv from hijacking uv's lookup.
    """
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


def _write_ai_configs(target_path: Path, env: str, profile: str, silent: bool = False):
    """Idempotently write/refresh the Claude + Gemini bootstrap configs.

    Merges into existing files rather than overwriting:
    - `.mcp.json`: replaces only the `valstorm` server entry, preserves any other servers.
    - `.claude/settings.json`: unions our default permissions allowlist with any existing entries.
    - `.gemini/settings.json`: replaces only the `valstorm` mcpServers entry; adds the
      inject-docs SessionStart hook only when `hooks` is absent (so user-customized hooks
      are preserved).

    Safe to re-run. Does NOT touch CLAUDE.md / GEMINI.md / README.md — those are owned
    by the user after init.
    """
    server_config = _build_mcp_server_config(env, profile)

    # 1. .mcp.json — Claude Code reads this for repo-scoped MCP servers.
    mcp_path = target_path / ".mcp.json"
    mcp_data = _load_json(mcp_path)
    mcp_data.setdefault("mcpServers", {})
    mcp_data["mcpServers"]["valstorm"] = server_config
    with open(mcp_path, "w") as f:
        json.dump(mcp_data, f, indent=4)

    # 2. .claude/settings.json — union the permissions allowlist with existing entries.
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

    # 3. .gemini/settings.json — set our mcpServers entry; only seed hooks when absent.
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

@app.command(name="update-stubs")
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

@app.command()
def pull(
    object_type: str = typer.Argument(None, help="Specific object type to pull (e.g., record_trigger)."),
    file_name: str = typer.Argument(None, help="Specific file to pull (e.g., trigger_name.py)."),
    manifest: str = typer.Option(None, "--manifest", "-m", help="Path to a deployment manifest JSON file."),
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
    
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    # 1. Fetch available schemas to see what we can pull
    with auth.get_client() as client:
        schema_res = client.get("/schema")
        if schema_res.status_code != 200:
            console.print("[bold red]Failed to fetch schemas.[/bold red]")
            raise typer.Exit(1)
        available_schemas = schema_res.json()

    # 2. Define target types
    manifest_data = None
    if manifest:
        manifest_path = Path(manifest)
        if not manifest_path.exists():
            console.print(f"[bold red]Manifest file not found:[/bold red] {manifest}")
            raise typer.Exit(1)
        with open(manifest_path, "r") as f:
            manifest_data = json.load(f).get("objects", {})
        target_types = [t for t in manifest_data.keys() if t in available_schemas]
    elif object_type:
        if object_type not in available_schemas:
            console.print(f"[bold red]Error:[/bold red] Object type '{object_type}' not found in schemas.")
            raise typer.Exit(1)
        target_types = [object_type]
    else:
        try:
            with open(root / "valstorm.json", "r") as f:
                config = json.load(f)
        except Exception:
            config = {}
            
        configured_objects = config.get("objects")
        
        if configured_objects:
            target_types = [t for t in configured_objects if t in available_schemas]
        else:
            core_types = ["record_trigger", "function"]
            metadata_types = [
                "ai_agent", "app", "app_page", "app_metadata", 
                "permission", "notification_setting", 
                "schedule_trigger_setting", "workspace"
            ]
            target_types = [t for t in (core_types + metadata_types) if t in available_schemas]
    
    if not target_types:
        console.print("[yellow]No matching objects found in schemas to pull records for.[/yellow]")
    
    for file_type in target_types:
        console.print(f"Pulling [cyan]{file_type}[/cyan]s from [blue]{get_api_base_url(auth.env)}[/blue]...")
        query = f"SELECT * FROM {file_type}"
        if manifest_data and file_type in manifest_data:
            files_to_pull = manifest_data[file_type]
            if isinstance(files_to_pull, list) and files_to_pull:
                conditions = " OR ".join([f"file_name = '{f}'" for f in files_to_pull])
                query += f" WHERE ({conditions})"
            elif isinstance(files_to_pull, list) and not files_to_pull:
                continue
        elif file_name:
            query += f" WHERE file_name = '{file_name}'"
        
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
                
            if file_name:
                records = [r for r in records if r.get("file_name") == file_name]

            target_dir = root / "object" / file_type
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Clean up old monolithic metadata file if it exists
            old_meta = target_dir / f"{file_type}_metadata.json"
            if old_meta.exists():
                try:
                    old_meta.unlink()
                except Exception:
                    pass

            count = 0
            code_count = 0
            for record in records:
                count += 1
                
                # Save individual metadata
                safe_name = "".join(c for c in str(record.get("name", "unnamed")) if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
                record_id = record.get("id", "noid")
                
                with open(target_dir / f"{safe_name}_{record_id}.json", "w") as f:
                    json.dump(record, f, indent=4)
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
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    console.print(f"Pulling [cyan]schemas[/cyan] from [blue]{get_api_base_url(auth.env)}[/blue]...")
    
    with auth.get_client() as client:
        # If specific object requested, use the specific endpoint if it's more efficient, 
        # but the current logic fetches all and filters. 
        # Actually /schema returns everything, let's keep it simple for now or check if /schema/{object} is better.
        endpoint = f"/schema/{object_type}" if object_type else "/schema"
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
    api_name: str = typer.Argument(None, help="Specific object directory to push (e.g., record_trigger)."),
    file_name: str = typer.Argument(None, help="Specific file to push (e.g., trigger_name.py)."),
    manifest: str = typer.Option(None, "--manifest", "-m", help="Path to a deployment manifest JSON file."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Upload local changes to the Valstorm cloud.
    """
    root = get_project_root()
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    object_root = root / "object"
    if not object_root.exists():
        console.print("[yellow]No 'object' directory found. Nothing to push.[/yellow]")
        return

    # Identify which types we have locally
    manifest_data = None
    if manifest:
        manifest_path = Path(manifest)
        if not manifest_path.exists():
            console.print(f"[bold red]Manifest file not found:[/bold red] {manifest}")
            raise typer.Exit(1)
        with open(manifest_path, "r") as f:
            manifest_data = json.load(f).get("objects", {})
        types = [t for t in manifest_data.keys() if (object_root / t).exists()]
    elif api_name:
        types = [api_name]
    else:
        types = [d.name for d in object_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
        
        # Filter types by configuration if present
        try:
            with open(root / "valstorm.json", "r") as f:
                config = json.load(f)
                configured_objects = config.get("objects")
                if configured_objects:
                    types = [t for t in types if t in configured_objects]
        except Exception:
            pass
    
    if not types:
        console.print("[yellow]No object types found in 'object' directory.[/yellow]")
        return

    for file_type in types:
        local_dir = object_root / file_type
        
        metadata = []
        # Load legacy monolithic file if present
        legacy_meta = local_dir / f"{file_type}_metadata.json"
        if legacy_meta.exists():
            try:
                with open(legacy_meta, "r") as f:
                    metadata.extend(json.load(f))
            except Exception:
                pass
                
        # Load individual JSON metadata files
        for meta_file in local_dir.glob("*.json"):
            if meta_file.name == f"{file_type}_metadata.json":
                continue
            try:
                with open(meta_file, "r") as f:
                    record_data = json.load(f)
                    if isinstance(record_data, dict):
                        metadata.append(record_data)
            except Exception:
                pass
            
        updates_payload = []
        creates_payload = []
        
        # Map current metadata for easy lookup
        meta_map = {r.get("file_name"): r for r in metadata if r.get("file_name")}
        
        # Scan local directory for changes and new files
        glob_pattern = file_name if file_name else "*.py"
        files_to_scan = []
        if manifest_data and file_type in manifest_data:
            manifest_files = manifest_data[file_type]
            if manifest_files == '*':
                files_to_scan = list(local_dir.glob(glob_pattern))
            elif isinstance(manifest_files, list):
                files_to_scan = [local_dir / f for f in manifest_files if (local_dir / f).exists()]
        else:
            files_to_scan = list(local_dir.glob(glob_pattern))

        for file_path in files_to_scan:
            current_file_name = file_path.name
            with open(file_path, "r") as f:
                local_code = f.read()
            
            if current_file_name in meta_map:
                # This is an existing file, check for updates
                record = meta_map[current_file_name]
                if local_code != record.get("code"):
                    updates_payload.append({
                        "id": record["id"],
                        "code": local_code,
                        "app": record.get("app")
                    })
            else:
                # This is a NEW file, we need to create it in the cloud
                console.print(f"Detected new local {file_type}: [cyan]{current_file_name}[/cyan]")
                if typer.confirm(f"Do you want to create {current_file_name} in the cloud?"):
                    name = typer.prompt(f"Display name for this {file_type}", default=current_file_name.replace(".py", "").replace("_", " ").title())
                    app_id = typer.prompt("App ID (The UUID of the Valstorm App this belongs to)")
                    
                    new_record = {
                        "name": name,
                        "file_name": current_file_name,
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
            for record in metadata:
                safe_name = "".join(c for c in str(record.get("name", "unnamed")) if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
                record_id = record.get("id", "noid")
                with open(local_dir / f"{safe_name}_{record_id}.json", "w") as f:
                    json.dump(record, f, indent=4)
        
        if not (creates_payload or updates_payload):
            console.print(f"No changes detected for [cyan]{file_type}[/cyan]s.")

@app.command(name="scaffold-web")
def scaffold_web(
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Override the output base directory for scaffolded web pages.")
):
    """
    Scaffold app pages (tagged Docs/Marketing) of type 'Web Page' into organized local Markdown files.
    """
    root = get_project_root()
    output_base_dir = Path(output_dir) if output_dir else root / "web"
    
    def progress_callback(event, **kwargs):
        if event == "scaffold":
            rec_tag = kwargs.get("tag")
            record = kwargs.get("record")
            tag_folder = kwargs.get("tag_folder")
            slug = kwargs.get("slug")
            console.print(f"Scaffolded: \\\\[[cyan]{rec_tag}[/cyan]] '{record.get('name')}' -> [green]{tag_folder}/{slug}.md[/green]")
        elif event == "skip":
            rec_tag = kwargs.get("tag")
            record = kwargs.get("record")
            console.print(f"[yellow]Warning:[/yellow] Page '{record.get('name')}' (ID: {record.get('id')}) has tag '{rec_tag}' but no slug. Skipping.")

    try:
        total_records, scaffolded_count, skipped_count, tag_counts = run_web_scaffolding(
            root_path=root,
            output_base_dir=output_base_dir,
            progress_callback=progress_callback
        )
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("[yellow]Hint: Run 'valstorm pull' first to sync metadata records from the cloud.[/yellow]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)
        
    console.print("\n" + "="*50)
    console.print("[bold green]SCAFFOLDING COMPLETED SUCCESSFULLY![/bold green]")
    console.print("="*50)
    console.print(f"Total Pages Processed: {scaffolded_count}")
    for t, count in tag_counts.items():
        console.print(f"  - {t}: {count} pages")
    if skipped_count > 0:
        console.print(f"Pages Skipped: {skipped_count}")
    console.print(f"All markdown files written to: [blue]{output_base_dir}[/blue]")
    console.print("="*50)

@app.command(name="push-web")
def push_web(
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Override the output base directory for scaffolded web pages."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Push local web pages (markdown documents with YAML frontmatter) from the web folder back to the Valstorm cloud.
    """
    root = get_project_root()
    output_base_dir = Path(output_dir) if output_dir else root / "web"
    metadata_path = root / "object" / "app_page" / "app_page_metadata.json"
    
    auth = get_auth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    if not output_base_dir.exists():
        console.print(f"[bold red]Error:[/bold red] Local web folder not found at {output_base_dir}")
        raise typer.Exit(1)
        
    console.print(f"Scanning local web pages in [blue]{output_base_dir}[/blue]...")
    
    try:
        creates_payload, updates_payload, merged_metadata = prepare_web_push(
            root_path=root,
            output_base_dir=output_base_dir
        )
    except ValueError as e:
        console.print(f"[bold red]Error preparing push:[/bold red] {e}")
        raise typer.Exit(1)
        
    if not creates_payload and not updates_payload:
        console.print("[yellow]No local changes or new files detected in the web folder.[/yellow]")
        return
        
    console.print(f"Found [green]{len(creates_payload)} new pages[/green] to create and [cyan]{len(updates_payload)} pages[/cyan] to update.")
    
    if not typer.confirm("Do you want to push these changes to the cloud?"):
        console.print("[yellow]Push cancelled.[/yellow]")
        return
        
    # 1. Handle Creates
    if creates_payload:
        console.print(f"Creating {len(creates_payload)} new pages on [blue]{get_api_base_url(auth.env)}[/blue]...")
        with auth.get_client() as client:
            response = client.post("/object/app_page", json=creates_payload)
            if response.status_code in [200, 201]:
                console.print("[bold green]✓ Successfully created new app pages.[/bold green]")
                newly_created = response.json() if isinstance(response.json(), list) else [response.json()]
                
                created_map = {r["slug"]: r for r in newly_created if r.get("slug")}
                for i, r in enumerate(merged_metadata):
                    if r.get("slug") in created_map:
                        merged_metadata[i] = created_map[r["slug"]]
            else:
                console.print(f"[bold red]Create failed:[/bold red] {response.status_code}")
                console.print(response.text)
                raise typer.Exit(1)
                
    # 2. Handle Updates
    if updates_payload:
        console.print(f"Updating {len(updates_payload)} existing pages on [blue]{get_api_base_url(auth.env)}[/blue]...")
        with auth.get_client() as client:
            response = client.patch("/object/app_page", json=updates_payload)
            if response.status_code in [200, 204]:
                console.print("[bold green]✓ Successfully updated existing app pages.[/bold green]")
                if response.status_code == 200:
                    updated_records = response.json() if isinstance(response.json(), list) else [response.json()]
                    updated_map = {r["id"]: r for r in updated_records if r.get("id")}
                    for i, r in enumerate(merged_metadata):
                        if r.get("id") in updated_map:
                            merged_metadata[i] = updated_map[r["id"]]
            else:
                console.print(f"[bold red]Update failed:[/bold red] {response.status_code}")
                console.print(response.text)
                raise typer.Exit(1)
                
    # Save the updated merged metadata JSON back to disk
    try:
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(merged_metadata, f, indent=4)
        console.print(f"[green]✓ Saved updated local metadata mapping to {metadata_path}[/green]")
    except Exception as e:
        console.print(f"[bold red]Error saving local metadata file:[/bold red] {e}")
        
    console.print("[bold green]✓ Push completed successfully![/bold green]")

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
    auth = get_auth(profile=profile, env=env)
    
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
    auth = get_auth(profile=profile, env=env)
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
    auth = get_auth(profile=profile, env=env)
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
    auth = get_auth(profile=profile, env=env)
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
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Must be run inside a Valstorm project.")
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


@app.command(name="scaffold-docs")
def scaffold_docs(
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    Fetch documentation records and scaffold them as Markdown files.
    """
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    try:
        root = get_project_root()
    except Exception:
        root = Path.cwd()
        
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    with auth.get_client() as client:
        try:
            response = client.post("/query", json={
                "query": "SELECT * FROM documentation"
            })
            
            if response.status_code != 200:
                console.print(f"[bold red]Query failed ({response.status_code}):[/bold red] {response.text}")
                raise typer.Exit(1)
                
            data = response.json()
            
            if not isinstance(data, list):
                console.print("[yellow]Expected a list of documentation records.[/yellow]")
                raise typer.Exit(1)
                
            console.print(f"Found {len(data)} documentation records. Scaffolding...")
            
            def tree_to_markdown(node):
                if not node:
                    return ""
                    
                if isinstance(node, list):
                    return "\n".join(tree_to_markdown(child) for child in node if child)
                
                md = ""
                component = node.get("component", "")
                props = node.get("props", {})
                if not component and "component_type" in props:
                    component = props["component_type"]
                    
                children = node.get("children", [])
                
                if component == "Typography":
                    variant = props.get("variant", "body1")
                    text = props.get("text", "")
                    
                    if variant == "h1":
                        md += f"# {text}\n\n"
                    elif variant == "h2":
                        md += f"## {text}\n\n"
                    elif variant == "h3":
                        md += f"### {text}\n\n"
                    elif variant == "h4":
                        md += f"#### {text}\n\n"
                    elif variant == "h5":
                        md += f"##### {text}\n\n"
                    elif variant == "h6":
                        md += f"###### {text}\n\n"
                    else:
                        md += f"{text}\n\n"
                elif component == "Text":
                    md += f"{props.get('text', '')}\n\n"
                elif component == "Paragraph":
                    md += f"{props.get('text', '')}\n\n"
                elif component == "RichText":
                    md += f"{props.get('value', '')}\n\n"
                
                for child in children:
                    child_md = tree_to_markdown(child)
                    if child_md:
                        md += child_md
                    
                return md

            for record in data:
                name = record.get("name", "untitled")
                slug = record.get("slug", "") or name
                category = record.get("category", "uncategorized")
                if not category:
                    category = "uncategorized"
                seo_title = record.get("seo_title", "")
                seo_description = record.get("seo_description", "")
                is_published = record.get("is_published", False)
                
                def sanitize(s):
                    import re
                    s = str(s).lower()
                    s = re.sub(r'[^a-z0-9]+', '-', s)
                    return s.strip('-')
                
                safe_category = sanitize(category)
                if not safe_category:
                    safe_category = "uncategorized"
                    
                safe_slug = sanitize(slug)
                if not safe_slug:
                    continue
                    
                cat_dir = docs_dir / safe_category
                cat_dir.mkdir(parents=True, exist_ok=True)
                
                file_path = cat_dir / f"{safe_slug}.md"
                
                frontmatter = "---\n"
                frontmatter += f"title: \"{name}\"\n"
                if seo_title:
                    frontmatter += f"seo_title: \"{seo_title}\"\n"
                if seo_description:
                    frontmatter += f"seo_description: \"{seo_description}\"\n"
                frontmatter += f"category: \"{category}\"\n"
                frontmatter += f"is_published: {str(is_published).lower()}\n"
                frontmatter += "---\n\n"
                
                content_json = record.get("content")
                md_body = ""
                
                if content_json:
                    if isinstance(content_json, str):
                        try:
                            content_data = json.loads(content_json)
                        except json.JSONDecodeError:
                            content_data = []
                    else:
                        content_data = content_json
                        
                    md_body = tree_to_markdown(content_data)
                    
                with open(file_path, "w") as f:
                    f.write(frontmatter + md_body)
                    
                console.print(f"[green]✓[/green] Created {file_path.relative_to(root)}")
                
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

if __name__ == "__main__":
    app()



