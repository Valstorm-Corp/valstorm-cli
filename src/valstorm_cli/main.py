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
from rich.console import Console


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
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name to save these credentials under."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment (local, dev, prod)."),
    use_password: bool = typer.Option(False, "--password", help="Use legacy password flow.")
):
    """
    Authenticate with Valstorm.
    """
    auth = get_auth(profile=profile, env=env)
    
    console.print(f"Logging in to [blue]{get_api_base_url(auth.env)}[/blue] (Profile: [cyan]{auth.profile}[/cyan])")
    
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
def sql_query(
    query: str = typer.Argument(..., help="The SQL query to execute."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    output: str = typer.Option("table", "--output", "-o", help="Output format (table, json)."),
    bypass_cache: bool = typer.Option(False, "--bypass-cache", help="Bypass the query cache."),
    save: Optional[str] = typer.Option(None, "--save", "-s", help="Save results to a JSON file."),
    csv: Optional[str] = typer.Option(None, "--csv", help="Save results to a CSV file.")
):
    """
    Execute a SQL-like query against the Valstorm API.
    """
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        try:
            response = client.post("/query", json={
                "query": query,
                "bypass_cache": bypass_cache
            })
            
            if response.status_code != 200:
                console.print(f"[bold red]Query failed ({response.status_code}):[/bold red] {response.text}")
                raise typer.Exit(1)
                
            data = response.json()
            
            # Save logic
            if save:
                with open(save, 'w') as f:
                    json.dump(data, f, indent=4)
                console.print(f"[green]✓ Results saved to {save}[/green]")
                
            if csv:
                if isinstance(data, list) and len(data) > 0:
                    import csv
                    keys = data[0].keys()
                    with open(csv, 'w', newline='') as f:
                        dict_writer = csv.DictWriter(f, fieldnames=keys)
                        dict_writer.writeheader()
                        dict_writer.writerows(data)
                    console.print(f"[green]✓ Results saved to {csv}[/green]")
                elif isinstance(data, dict):
                    import csv
                    keys = data.keys()
                    with open(csv, 'w', newline='') as f:
                        dict_writer = csv.DictWriter(f, fieldnames=keys)
                        dict_writer.writeheader()
                        dict_writer.writerow(data)
                    console.print(f"[green]✓ Results saved to {csv}[/green]")
                else:
                    console.print("[yellow]Cannot save non-list/dict data as CSV.[/yellow]")

            if output == "json":
                console.print_json(data=data)
            else:
                if not data:
                    console.print("[yellow]No records found.[/yellow]")
                    return
                
                from rich.table import Table
                table = Table(show_header=True, header_style="bold magenta")
                
                # Get columns from first record
                if isinstance(data, list) and len(data) > 0:
                    columns = data[0].keys()
                    for col in columns:
                        table.add_column(col)
                        
                    for row in data:
                        table.add_row(*[str(row.get(col, "")) for col in columns])
                    
                    console.print(table)
                    console.print(f"\n[dim]Total records: {len(data)}[/dim]")
                elif isinstance(data, dict):
                    # Handle single record if applicable
                    columns = data.keys()
                    for col in columns:
                        table.add_column(col)
                    table.add_row(*[str(data.get(col, "")) for col in columns])
                    console.print(table)
                else:
                    console.print(data)
                    
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
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
valstorm pull   # pull existing objects/schemas
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

    # 6. Bootstrap Gemini Settings
    gemini_dir = target_path / ".gemini"
    gemini_dir.mkdir(exist_ok=True)
    gemini_settings = {
        "mcpServers": {
            "valstorm": {
                "command": "uv",
                "args": ["run", "--directory", ".", "python", "run_mcp.py"],
                "env": {
                    "VALSTORM_ENV": auth.env,
                    "VALSTORM_PROFILE": auth.profile,
                    "VIRTUAL_ENV": ""
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

    # 7. Bootstrap Claude Code MCP server — .mcp.json at project root.
    # Claude Code reads .mcp.json (not .claude/settings.json) for repo-scoped MCP servers.
    # VIRTUAL_ENV="" blocks an inherited shell venv from hijacking uv's lookup.
    mcp_config = {
        "mcpServers": {
            "valstorm": {
                "command": "uv",
                "args": ["run", "--directory", ".", "python", "run_mcp.py"],
                "env": {
                    "VALSTORM_ENV": auth.env,
                    "VALSTORM_PROFILE": auth.profile,
                    "VIRTUAL_ENV": ""
                }
            }
        }
    }
    with open(target_path / ".mcp.json", "w") as f:
        json.dump(mcp_config, f, indent=4)
    console.print("[green]✓[/green] Claude MCP server registered in .mcp.json.")

    # 7b. Permissions allowlist so common read-only tools don't prompt on first use.
    claude_dir = target_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    claude_settings = {
        "permissions": {
            "allow": [
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
                "mcp__valstorm__run_sql_query"
            ]
        }
    }
    with open(claude_dir / "settings.json", "w") as f:
        json.dump(claude_settings, f, indent=4)
    console.print("[green]✓[/green] Claude permissions allowlist bootstrapped.")

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

# 3. Pull existing objects/schemas from your org
valstorm pull
```

After `uv sync`, Claude Code and Gemini CLI will be able to launch the
Valstorm MCP server. Start a session in this directory and the `valstorm`
MCP tools (e.g. `run_sql_query`, `get_me`) will appear.

## Commands

```bash
# Pull remote objects/schemas to local filesystem
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
    
    auth = get_auth(profile=profile, env=env)
    
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
    auth = get_auth(profile=profile, env=env)
    
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
    auth = get_auth(profile=profile, env=env)
    
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

if __name__ == "__main__":
    app()
