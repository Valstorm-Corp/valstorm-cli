# Compiled Context

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/auth_cmds.py

```python
import typer
import httpx
import json
import secrets
import hashlib
import base64
import threading
import time
import webbrowser
from typing import Optional
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from rich.console import Console
from .auth import get_auth, get_api_base_url, find_project_root, get_project_root, load_config

console = Console()
auth_app = typer.Typer(help="Manage Valstorm authentication profiles and sessions.")







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
        root = get_project_root()
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
        console.print("\n[dim]* Indicates currently targeted profile in valstorm.json[/dim]")

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

@auth_app.command()
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
                
                console.print("Opening browser for authentication...")
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

@auth_app.command(name="logout")
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
        root = get_project_root()
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

@auth_app.command()
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

def get_pkce_pair():
    verifier = secrets.token_urlsafe(32)
    challenge_hash = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(challenge_hash).decode("utf-8").rstrip("=")
    return verifier, challenge


# Personal Access Tokens (PATs) Management
pat_app = typer.Typer(help="Manage Personal Access Tokens (PATs).")

@pat_app.command(name="create")
def pat_create(
    name: str = typer.Argument(..., help="A name for this Personal Access Token."),
    expires_in_days: Optional[int] = typer.Option(30, "--expires", "-x", help="Expiration time in days. Use 0 or null for no expiration."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Authentication profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    Create a new Personal Access Token (PAT).
    """
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    payload: dict = {
        "name": name,
    }
    if expires_in_days is not None and expires_in_days > 0:
        payload["expires_in_days"] = expires_in_days
    else:
        payload["expires_in_days"] = None

    with auth.get_client() as client:
        res = client.post("/auth/pats", json=payload)
        if res.status_code == 200:
            data = res.json()
            console.print("[bold green]✓ Personal Access Token created successfully![/bold green]")
            console.print(f"Name: [bold cyan]{data['name']}[/bold cyan]")
            console.print(f"ID: [bold]{data['id']}[/bold]")
            if data.get('expires_at'):
                console.print(f"Expires At: [yellow]{data['expires_at']}[/yellow]")
            else:
                console.print("Expires At: [yellow]Never[/yellow]")
            console.print("\n[bold red]IMPORTANT: Copy the token below. It will not be shown again.[/bold red]")
            console.print(f"[bold green]{data['token']}[/bold green]\n")
        else:
            console.print(f"[bold red]Failed to create PAT:[/bold red] {res.status_code}")
            console.print(res.text)
            raise typer.Exit(1)

@pat_app.command(name="list")
def pat_list(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Authentication profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    List your active Personal Access Tokens (PATs).
    """
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        res = client.get("/auth/pats")
        if res.status_code == 200:
            pats = res.json()
            if not pats:
                console.print("[yellow]You have no active Personal Access Tokens.[/yellow]")
                return
            
            from rich.table import Table
            table = Table(title="Personal Access Tokens (PATs)")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="bold")
            table.add_column("Created At", style="green")
            table.add_column("Expires At", style="yellow")
            table.add_column("Last Used At", style="magenta")
            
            for p in pats:
                expires_at = p.get("expires_at") or "Never"
                last_used = p.get("last_used_at") or "Never"
                table.add_row(
                    p["id"],
                    p["name"],
                    p["created_at"],
                    expires_at,
                    last_used
                )
            console.print(table)
        else:
            console.print(f"[bold red]Failed to list PATs:[/bold red] {res.status_code}")
            console.print(res.text)
            raise typer.Exit(1)

@pat_app.command(name="revoke")
def pat_revoke(
    pat_id: str = typer.Argument(..., help="The ID of the Personal Access Token to revoke."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Authentication profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    Revoke a Personal Access Token (PAT).
    """
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        res = client.delete(f"/auth/pats/{pat_id}")
        if res.status_code == 200:
            console.print(f"[bold green]✓ PAT '{pat_id}' successfully revoked.[/bold green]")
        else:
            console.print(f"[bold red]Failed to revoke PAT:[/bold red] {res.status_code}")
            console.print(res.text)
            raise typer.Exit(1)

@pat_app.command(name="delete", hidden=True)
def pat_delete(
    pat_id: str = typer.Argument(..., help="The ID of the Personal Access Token to revoke."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Authentication profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    Revoke a Personal Access Token (PAT) (alias for revoke).
    """
    pat_revoke(pat_id=pat_id, profile=profile, env=env)

auth_app.add_typer(pat_app, name="pat")


```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/auth.py

```python
import json
import os
import sys
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

import httpx
console = Console()

def decode_jwt_payload(token: str) -> dict:
    import base64
    import json
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1]
        padding = len(payload_b64) % 4
        if padding:
            payload_b64 += "=" * (4 - padding)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return {}

# Configuration
ENVIRONMENTS = {
    "prod": "https://api.valstorm.com",
    "dev": "https://api-dev.valstorm.com",
    "local": "http://localhost:8010",
    "blue": "http://localhost:8011",
    "green": "http://localhost:8021"
}

WEB_ENVIRONMENTS = {
    "prod": "https://app.valstorm.com",
    "dev": "https://app-dev.valstorm.com",
    "local": "http://localhost:3000",
    "blue": "http://localhost:3000",
    "green": "http://localhost:3000"
}

def _load_workspace_config() -> dict:
    """Helper to find and load valstorm.json by searching upwards."""
    current = Path.cwd()
    while current != current.parent:
        config_path = current / "valstorm.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
            break
        current = current.parent
    return {}

def get_env() -> str:
    if "VALSTORM_ENV" in os.environ:
        return os.environ["VALSTORM_ENV"].lower()
    config = _load_workspace_config()
    return config.get("env", "prod").lower()

def get_profile() -> str:
    if "VALSTORM_PROFILE" in os.environ:
        return os.environ["VALSTORM_PROFILE"].lower()
    config = _load_workspace_config()
    return config.get("profile", "default").lower()

def get_sandbox() -> Optional[str]:
    config = _load_workspace_config()
    val = config.get("sandbox")
    return val.lower() if val else None

def get_base_url(env: str = None) -> str:
    env = env or get_env()
    return ENVIRONMENTS.get(env, ENVIRONMENTS["prod"])

def get_web_url(env: str = None) -> str:
    env = env or get_env()
    return WEB_ENVIRONMENTS.get(env, WEB_ENVIRONMENTS["prod"])

def get_api_base_url(env: str = None) -> str:
    return f"{get_base_url(env)}/v1"

def get_auth_file(env: str, profile: str) -> Path:
    """Helper to get the auth file path for a specific environment and profile."""
    auth_dir = Path.home() / ".valstorm"
    
    # 1. Try the new standard pattern: auth_{env}_{profile}.json
    new_path = auth_dir / f"auth_{env}_{profile}.json"
    if new_path.exists():
        return new_path
    
    # 2. Fallback for legacy pattern if profile is 'default': auth_{env}.json
    if profile == "default":
        legacy_path = auth_dir / f"auth_{env}.json"
        if legacy_path.exists():
            return legacy_path
            
    # 3. Default to the new pattern for new files
    return new_path


class ValstormAuth:
    _validation_cache = {} # (env, profile) -> bool

    def __init__(self, profile: str = None, env: str = None, use_parent: bool = False):
        self.profile = profile or get_profile()
        self.env = env or get_env()
        self.sandbox = None if use_parent else get_sandbox()
        self.access_token = None
        self.refresh_token = None
        self.organization_name = None
        self.default_app_id = None
        self._load_tokens()

    @property
    def auth_file(self) -> Path:
        return get_auth_file(self.env, self.profile)

    def _load_tokens(self):
        # Reset current tokens before loading
        self.access_token = None
        self.refresh_token = None
        self.organization_name = None
        self.default_app_id = None
        
        if self.auth_file.exists():
            try:
                content = self.auth_file.read_text().strip()
                if not content:
                    return
                data = json.loads(content)
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.organization_name = data.get("organization_name")
                self.default_app_id = data.get("default_app_id")

            except (json.JSONDecodeError, Exception):
                # If file is corrupted or unreadable, we ignore it 
                # so ensure_valid_token will return False and trigger a re-login
                pass

    def save_tokens(self, access_token: str, refresh_token: str = None, organization_name: str = None, default_app_id: str = None):
        if access_token:
            self.access_token = access_token
        if refresh_token is not None:
            self.refresh_token = refresh_token
        if organization_name is not None:
            self.organization_name = organization_name
        if default_app_id is not None:
            self.default_app_id = default_app_id
            
        try:
            self.auth_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "organization_name": self.organization_name,
                "default_app_id": self.default_app_id
            }

            # Write to a temporary file first then rename to ensure atomicity
            temp_file = self.auth_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(data, indent=2))
            temp_file.replace(self.auth_file)
        except Exception as e:
            print(f"Error saving tokens for profile {self.profile}: {e}", file=sys.stderr)


    def get_client(self) -> httpx.Client:
        """Returns a synchronous HTTPX client configured with auth headers."""
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return httpx.Client(base_url=get_api_base_url(self.env), headers=headers, timeout=10.0)

    def refresh_auth(self) -> bool:
        if not self.refresh_token:
            return False
        
        try:
            with httpx.Client(base_url=get_api_base_url(self.env), timeout=10.0) as client:
                response = client.post("/oauth2/refresh", json={"refresh_token": self.refresh_token})
                if response.status_code == 200:
                    data = response.json()
                    new_access = data.get("access_token")
                    new_refresh = data.get("refresh_token", self.refresh_token)
                    self.save_tokens(access_token=new_access, refresh_token=new_refresh)
                    return True
                else:
                    return False
        except Exception:
            # print(f"Error refreshing token: {e}", file=sys.stderr)
            return False

    def _get_cached_sandbox_token(self, sandbox_name: str) -> Optional[str]:
        if self.auth_file.exists():
            try:
                data = json.loads(self.auth_file.read_text())
                sandboxes = data.get("sandboxes", {})
                sandbox_data = sandboxes.get(sandbox_name, {})
                expires_at_str = sandbox_data.get("expires_at")
                if expires_at_str:
                    import datetime
                    expires_at = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    if datetime.datetime.now(datetime.timezone.utc) > expires_at:
                        return None
                return sandbox_data.get("access_token")
            except Exception:
                pass
        return None

    def _save_sandbox_token(self, sandbox_name: str, token: str):
        payload = decode_jwt_payload(token)
        expires_at = None
        if payload.get("exp"):
            import datetime
            expires_at = datetime.datetime.fromtimestamp(payload["exp"], datetime.timezone.utc).isoformat()
            
        try:
            self.auth_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if self.auth_file.exists():
                try:
                    data = json.loads(self.auth_file.read_text())
                except Exception:
                    pass
            
            data["access_token"] = data.get("access_token", self.access_token)
            data["refresh_token"] = data.get("refresh_token", self.refresh_token)
            data["organization_name"] = data.get("organization_name", self.organization_name)
            data["default_app_id"] = data.get("default_app_id", self.default_app_id)
            
            if "sandboxes" not in data:
                data["sandboxes"] = {}
                
            data["sandboxes"][sandbox_name] = {
                "access_token": token,
                "expires_at": expires_at
            }
            
            temp_file = self.auth_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(data, indent=2))
            temp_file.replace(self.auth_file)
        except Exception as e:
            print(f"Error saving sandbox token: {e}", file=sys.stderr)

    def _validate_sandbox_token(self, token: str) -> bool:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            with httpx.Client(base_url=get_api_base_url(self.env), headers=headers, timeout=5.0) as client:
                res = client.get("/auth/load")
                return res.status_code == 200
        except Exception:
            return False

    def _switch_to_sandbox_org(self, parent_token: str, sandbox_org_id: str) -> Optional[str]:
        headers = {"Authorization": f"Bearer {parent_token}"}
        try:
            with httpx.Client(base_url=get_api_base_url(self.env), headers=headers, timeout=10.0) as client:
                res = client.post("auth/switch", json={"id": sandbox_org_id})
                if res.status_code == 200:
                    return res.json().get("access_token")
                else:
                    console.print(f"[yellow]Switch organization failed ({res.status_code}): {res.text}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error connecting to API to switch organization: {e}[/red]")
        return None

    def ensure_valid_token(self) -> bool:
        """Checks if the token is valid, attempting to refresh if it's not."""
        if self.sandbox:
            # 1. Validate parent token first
            parent_auth = ValstormAuth(profile=self.profile, env=self.env, use_parent=True)
            if not parent_auth.ensure_valid_token():
                return False
            
            # Since parent_auth may have refreshed the parent token, we reload our tokens
            self._load_tokens()
            parent_token = parent_auth.access_token
            if not parent_token:
                console.print("[red]Could not retrieve parent authentication token.[/red]")
                return False
            
            # 2. Get sandbox token
            parent_payload = decode_jwt_payload(parent_token)
            parent_org_id = parent_payload.get("org")
            if not parent_org_id:
                console.print("[red]Could not extract parent organization ID from authentication token.[/red]")
                return False
                
            # Sanitize/generate api_name to match backend sandbox ID generation
            import re
            cleaned_sandbox = re.sub(r'[^a-zA-Z0-9_]', '', self.sandbox.lower().replace(" ", "_")).strip()
            cleaned_sandbox = re.sub(r'_+', '_', cleaned_sandbox)
            if not cleaned_sandbox:
                cleaned_sandbox = "env"
            api_name = cleaned_sandbox[:12]
            
            sandbox_org_id = f"{parent_org_id}_s_{api_name}"
            
            cached_sandbox_token = self._get_cached_sandbox_token(self.sandbox)
            if cached_sandbox_token:
                if self._validate_sandbox_token(cached_sandbox_token):
                    self.access_token = cached_sandbox_token
                    return True
            
            console.print(f"Authenticating into sandbox [bold cyan]{self.sandbox}[/bold cyan]...")
            new_sandbox_token = self._switch_to_sandbox_org(parent_token, sandbox_org_id)
            if new_sandbox_token:
                self._save_sandbox_token(self.sandbox, new_sandbox_token)
                self.access_token = new_sandbox_token
                return True
            else:
                console.print(f"[red]Failed to authenticate into sandbox '{self.sandbox}'.[/red]")
                return False

        cache_key = (self.env, self.profile)
        if ValstormAuth._validation_cache.get(cache_key):
            console.print(f"[green]Token for profile '{self.profile}' in environment '{self.env}' is valid (cached).[/green]")
            return True

        if not self.access_token:
            console.print(f"[yellow]No access token found for profile '{self.profile}' in environment '{self.env}'. Please log in.[/yellow]")
            return False
            
        try:
            with self.get_client() as client:
                response = client.get("/auth/load")
                if response.status_code == 200:
                    user_data = response.json()
                    user = user_data.get("user", user_data)
                    if user.get("organization_name"):
                        self.save_tokens(access_token=self.access_token, organization_name=user.get("organization_name"))
                    
                    ValstormAuth._validation_cache[cache_key] = True
                    console.print(f"[green]Token for profile '{self.profile}' in environment '{self.env}' is valid.[/green]")
                    return True
                
                if response.status_code == 401:
                    success = self.refresh_auth()
                    if success:
                        ValstormAuth._validation_cache[cache_key] = True
                    console.print(f"[yellow]Access token for profile '{self.profile}' in environment '{self.env}' was invalid. {'Successfully refreshed.' if success else 'Failed to refresh, please log in again.'}[/yellow]")
                    return success
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # If server is unreachable, we can't validate, but we don't want to spam error messages
            # Return False and let the command handle the failure
            console.print(f"[red]Unable to connect to Valstorm API at {get_api_base_url(self.env)} to validate token. Please check your network connection and try again.[/red]")
            return False
        except Exception:
            console.print(f"[red]An error occurred while validating the token for profile '{self.profile}' in environment '{self.env}'. Please try logging in again.[/red]")
            return False
        console.print(f"[red]Unexpected error validating token for profile '{self.profile}' in environment '{self.env}'. Please log in again.[/red]")
        return False


def find_project_root() -> Optional[Path]:
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
    raise typer.Exit(1)

def load_config(root: Path) -> dict:
    with open(root / "valstorm.json", "r") as f:
        return json.load(f)

def get_auth(profile: Optional[str] = None, env: Optional[str] = None, use_parent: bool = False) -> 'ValstormAuth':
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

    return ValstormAuth(profile=auth_profile, env=auth_env, use_parent=use_parent)

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/bundler.py

```python
import json
from pathlib import Path
from typing import Dict, Any, List

def bundle_local_app(app_config_path: Path, workspace_root: Path) -> Dict[str, Any]:
    """
    Reads an app.json config, compiles all associated schemas, and auto-discovers/collects
    all local object metadata records and python source files belonging to the app.
    """
    with open(app_config_path, "r") as f:
        app_config = json.load(f)
        
    app_id = app_config.get("id")
    if not app_id:
        raise ValueError("The 'id' (UUID) of the app is required in the configuration.")
        
    bundle = {
        "id": app_id,
        "name": app_config.get("name", "Unnamed App"),
        "description": app_config.get("description", ""),
        "schemas": [],
        "records": {}
    }
    
    # 1. Resolve and Bundle Schemas
    schemas_dir = workspace_root / "schemas"
    schemas_to_bundle: List[str] = app_config.get("schemas", [])
    
    # Auto-discover schemas if schemas_dir exists
    if schemas_dir.exists():
        for schema_file in schemas_dir.glob("*.json"):
            try:
                with open(schema_file, "r") as sf:
                    schema_data = json.load(sf)
                # If schema belongs to this app or is listed explicitly
                if schema_data.get("app") == app_id or schema_file.stem in schemas_to_bundle:
                    bundle["schemas"].append(schema_data)
            except Exception:
                pass
                
    # 2. Resolve and Bundle Records (functions, record_triggers, workspaces, etc.)
    object_root = workspace_root / "object"
    if object_root.exists():
        for type_dir in object_root.iterdir():
            if not type_dir.is_dir() or type_dir.name.startswith("."):
                continue
                
            file_type = type_dir.name
            type_records = []
            
            # Map of python files to their metadata JSON definitions
            code_files = list(type_dir.glob("*.py"))
            metadata_files = list(type_dir.glob("*.json"))
            
            # Exclude monolith metadata if present
            metadata_files = [m for m in metadata_files if m.name != f"{file_type}_metadata.json"]
            
            # Read metadata JSONs to identify records belonging to this app
            for meta_file in metadata_files:
                try:
                    with open(meta_file, "r") as mf:
                        meta_data = json.load(mf)
                    
                    # Verify if this record belongs to our target app
                    is_app_member = meta_data.get("app") == app_id
                    
                    # Also check if listed in explicit records of config (if provided)
                    explicit_records = app_config.get("records", {}).get(file_type, [])
                    is_explicit = False
                    for er in explicit_records:
                        if isinstance(er, str):
                            if meta_data.get("file_name") == er or meta_file.name == er:
                                is_explicit = True
                                break
                        elif isinstance(er, dict):
                            if meta_data.get("id") and meta_data.get("id") == er.get("id"):
                                is_explicit = True
                                break
                            elif meta_data.get("file_name") and meta_data.get("file_name") == er.get("file_name"):
                                is_explicit = True
                                break
                    
                    if is_app_member or is_explicit:
                        # If there is a matching code file, read the code on-disk to make sure we push current code
                        file_name = meta_data.get("file_name")
                        if file_name:
                            code_file_path = type_dir / file_name
                            if code_file_path.exists():
                                with open(code_file_path, "r") as cf:
                                    meta_data["code"] = cf.read()
                                    
                        type_records.append(meta_data)
                except Exception:
                    pass
                    
            # If explicit listings were specified but didn't have metadata JSON files,
            # we can create skeleton records for them, or append the dict directly
            explicit_records = app_config.get("records", {}).get(file_type, [])
            for er in explicit_records:
                if isinstance(er, str):
                    # Check if already added
                    if any(r.get("file_name") == er for r in type_records):
                        continue
                        
                    file_path = type_dir / er
                    if file_path.exists():
                        try:
                            with open(file_path, "r") as f_code:
                                code_content = f_code.read()
                            
                            # Generate basic skeleton
                            skeleton = {
                                "name": file_path.stem.replace("_", " ").title(),
                                "file_name": er,
                                "code": code_content,
                                "app": app_id,
                                "active": True
                            }
                            
                            # Set default trigger fields if applicable
                            if file_type == "record_trigger":
                                skeleton["object_api_name"] = "contact" # default fallback
                                skeleton["trigger_type"] = "after_upsert"
                                
                            type_records.append(skeleton)
                        except Exception:
                            pass
                elif isinstance(er, dict):
                    if any(r.get("id") == er.get("id") for r in type_records):
                        continue
                    
                    # Try to load the latest local code if a file_name is defined
                    file_name = er.get("file_name")
                    if file_name:
                        file_path = type_dir / file_name
                        if file_path.exists():
                            try:
                                with open(file_path, "r") as f_code:
                                    er["code"] = f_code.read()
                            except Exception:
                                pass
                    type_records.append(er)
                        
            if type_records:
                bundle["records"][file_type] = type_records
                
    return bundle

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/field.py

```python
import typer
import httpx
import json
from typing import Optional
from rich.console import Console
from .auth import ValstormAuth

console = Console()
field_app = typer.Typer(help="Manage schema fields", no_args_is_help=True)

@field_app.command(name="create")
def create_field(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema."),
    name: Optional[str] = typer.Option(None, "--name", help="Display name of the field."),
    api_name: Optional[str] = typer.Option(None, "--api-name", help="API name of the field."),
    type_: Optional[str] = typer.Option(None, "--type", help="Field type."),
    file: Optional[str] = typer.Option(None, "--file", help="JSON file containing field configuration."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Create a new field on an object."""
    payload = {}
    if file:
        try:
            with open(file, 'r') as f:
                payload = json.load(f)
        except Exception as e:
            console.print(f"[bold red]Failed to read file:[/bold red] {e}")
            raise typer.Exit(1)
    elif name and api_name and type_:
        payload = {"name": name, "api_name": api_name, "type": type_}
    else:
        console.print("[bold red]Must provide either --name, --api-name and --type, or --file.[/bold red]")
        raise typer.Exit(1)

    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.post(f"/schema/{schema_api_name}/field", json=payload)
            if res.status_code not in (200, 201):
                console.print(f"[bold red]Failed to create field:[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print("[green]✓ Successfully created field.[/green]")
            console.print_json(data=res.json())
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@field_app.command(name="update")
def update_field(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema."),
    field_api_name: str = typer.Argument(..., help="The API name of the field."),
    data: str = typer.Option(..., "--data", help="JSON string of field configuration to update."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Update an existing field's configuration."""
    try:
        payload = json.loads(data)
    except Exception as e:
        console.print(f"[bold red]Failed to parse JSON data:[/bold red] {e}")
        raise typer.Exit(1)

    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.patch(f"/schema/{schema_api_name}/field/{field_api_name}", json=payload)
            if res.status_code != 200:
                console.print(f"[bold red]Failed to update field:[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print("[green]✓ Successfully updated field.[/green]")
            console.print_json(data=res.json())
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@field_app.command(name="delete")
def delete_field(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema."),
    field_api_name: str = typer.Argument(..., help="The API name of the field."),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Delete a field."""
    if not confirm:
        if not typer.confirm(f"Are you sure you want to delete field '{field_api_name}' from schema '{schema_api_name}'?"):
            raise typer.Exit()

    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.delete(f"/schema/{schema_api_name}/field/{field_api_name}")
            if res.status_code != 200:
                console.print(f"[bold red]Failed to delete field:[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print(f"[green]✓ Successfully deleted field '{field_api_name}'.[/green]")
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/git_utils.py

```python
import subprocess
from pathlib import Path
from typing import Set, Optional

def get_git_root() -> Path:
    """
    Returns the absolute path to the root of the git repository.
    Raises RuntimeError if not inside a git repository.
    """
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        return Path(res.stdout.strip())
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Not inside a git repository") from e

def get_git_diff_files(ref: Optional[str] = None) -> Set[Path]:
    """
    Retrieves the absolute paths of all modified/added files.
    If ref is provided, diffs against that reference (commit, branch, tag, etc.).
    If ref is NOT provided, diffs against HEAD (including staged & unstaged modifications)
    and also fetches local untracked files.
    """
    root = get_git_root()
    files = set()
    
    # 1. Validate the reference if provided
    if ref:
        # Check if the ref exists via git rev-parse
        check_rev = subprocess.run(["git", "rev-parse", "--verify", ref], capture_output=True)
        if check_rev.returncode != 0:
            raise ValueError(f"Invalid git reference: {ref}")
            
    # 2. Query git diff for modified, added, renamed, or copied files
    # We use --name-only and --diff-filter to avoid including deleted files (since we want to deploy existing files)
    cmd = ["git", "diff", "--name-only", "--diff-filter=d"]
    if ref:
        cmd.append(ref)
        
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            line_stripped = line.strip()
            if line_stripped:
                files.add(root / line_stripped)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git diff command failed: {e.stderr}")
        
    # 3. If no reference is provided, also fetch uncommitted/untracked new files using status or diff
    if not ref:
        # Also include staged files if they are new or modified
        try:
            staged_res = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=d"], capture_output=True, text=True, check=True)
            for line in staged_res.stdout.splitlines():
                line_stripped = line.strip()
                if line_stripped:
                    files.add(root / line_stripped)
        except subprocess.CalledProcessError:
            pass

        # Include untracked files
        try:
            status_res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
            for line in status_res.stdout.splitlines():
                if line.startswith("?? "):
                    # Extract the filename part
                    file_rel = line[3:].strip()
                    if file_rel:
                        # Strip surrounding quotes if git printed them (for filenames with spaces)
                        if file_rel.startswith('"') and file_rel.endswith('"'):
                            file_rel = file_rel[1:-1]
                        files.add(root / file_rel)
        except subprocess.CalledProcessError:
            pass
            
    return files

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/hermes_cmds.py

```python
import typer
import subprocess
import shutil
import os
import json
from pathlib import Path
from rich.console import Console

hermes_app = typer.Typer(help="Manage distributed Hermes Agentic Networks", no_args_is_help=True)
console = Console()

HERMES_HOME = Path.home() / ".hermes"
NETWORK_DIR = HERMES_HOME / ".valstorm-network"
PROFILES_DIR = HERMES_HOME / "profiles"
SOURCES_FILE = NETWORK_DIR / "sources.json"


def ensure_git():
    if not shutil.which("git"):
        console.print("[bold red]Error:[/bold red] Git is required but not installed.")
        raise typer.Exit(1)


def load_sources() -> dict:
    """Load the sources.json state file. Returns {"sources": {...}} (empty dict of sources if missing/corrupt)."""
    if not SOURCES_FILE.exists():
        return {"sources": {}}
    try:
        with open(SOURCES_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "sources" not in data:
            return {"sources": {}}
        return data
    except (json.JSONDecodeError, OSError):
        return {"sources": {}}


def save_sources(data: dict) -> None:
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    with open(SOURCES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _derive_source_name(repo_url: str) -> str:
    """Derive a source slug from a repo URL's basename, stripping a trailing .git."""
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[: -len(".git")]
    return name


def _migrate_legacy_single_source():
    """
    Backward-compat migration: if NETWORK_DIR/.git exists (old single-repo layout)
    but sources.json does not, move the existing clone into NETWORK_DIR/default/
    and register it as a source named 'default'.
    """
    if SOURCES_FILE.exists():
        return
    if not (NETWORK_DIR / ".git").exists():
        return

    console.print("[yellow]Detected legacy single-source network layout. Migrating to multi-source layout...[/yellow]")

    default_dir = NETWORK_DIR / "default"
    tmp_dir = NETWORK_DIR.parent / ".valstorm-network-migrate-tmp"

    # Best-effort: read the origin remote before we move anything.
    repo_url = ""
    try:
        res = subprocess.run(
            ["git", "-C", str(NETWORK_DIR), "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
        if res.returncode == 0:
            repo_url = res.stdout.strip()
    except OSError:
        pass

    # Move NETWORK_DIR itself (with all its content, including .git) to a temp
    # location, then recreate NETWORK_DIR fresh and move the temp dir into
    # NETWORK_DIR/default/.
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    shutil.move(str(NETWORK_DIR), str(tmp_dir))
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp_dir), str(default_dir))

    data = {"sources": {"default": {"repo_url": repo_url}}}
    save_sources(data)

    console.print(f"[green]Migrated legacy network into {default_dir}[/green]")
    console.print(
        "[yellow]Your existing profiles in ~/.hermes/profiles/* pointed at the old paths and are now stale. "
        "Run 'valstorm hermes sync' to update profiles at their new locations.[/yellow]"
    )


def run_hermes(profile, args, capture=True):
    """Subprocess wrapper for the `hermes` CLI, mirroring the standalone sync-profile-credentials script."""
    cmd = ["hermes"]
    if profile:
        cmd += ["-p", profile]
    cmd += args
    return subprocess.run(cmd, capture_output=capture, text=True)


def profile_dir(profile):
    """Resolve a profile's home directory via `hermes config path` (read-side inspection only)."""
    r = run_hermes(profile, ["config", "path"])
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"Could not resolve config path for profile {profile!r}: {r.stderr.strip()}")
    return Path(r.stdout.strip()).parent


def _config_get(profile, key):
    r = run_hermes(profile, ["config", "get", key])
    if r.returncode != 0:
        return None
    value = r.stdout.strip()
    return value or None


def _config_set(profile, key, value):
    r = run_hermes(profile, ["config", "set", key, value])
    return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())


def sync_model_config(source, target):
    """Backfill model.default/model.provider from source (default profile if None) into target.

    Additive-only: if `target` already has its own model configured — e.g. a
    newly-linked network profile whose config.example.yaml was just copied to
    config.yaml with an intentional model tier (see model.md) — that tier is
    left untouched. Only profiles with NO model configured at all (blank
    config, no example, or the source's model.default is empty) fall back to
    copying the source's model. Without this guard, every profile in an
    agentic network silently collapses onto whatever model the default
    profile happens to use, defeating tiered model allocation entirely.
    """
    existing_model = _config_get(target, "model.default")
    existing_provider = _config_get(target, "model.provider")
    if existing_model and existing_provider:
        return
    default_model = _config_get(source, "model.default")
    provider = _config_get(source, "model.provider")
    if not default_model or not provider:
        return
    for key, value in (("model.default", default_model), ("model.provider", provider)):
        _config_set(target, key, value)


def load_auth_pool(profile_dir_path):
    auth_file = profile_dir_path / "auth.json"
    if not auth_file.exists():
        return {}
    with auth_file.open() as f:
        return json.load(f)


def read_env_file(path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_env_var(path, key, value):
    """Set key=value in an env file, replacing an existing line for that key."""
    existing = read_env_file(path)
    if existing.get(key) == value:
        return "unchanged"
    lines = path.read_text().splitlines() if path.exists() else []
    replaced = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") and not stripped.startswith("#"):
            new_lines.append(f"{key}={value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines) + "\n")
    path.chmod(0o600)
    return "updated" if replaced else "added"


def sync_credentials(source, target, include_oauth=False):
    """Copy provider/env credentials from source (default profile if None) into target."""
    src_dir = profile_dir(source)
    tgt_dir = profile_dir(target)

    src_auth = load_auth_pool(src_dir)
    tgt_auth = load_auth_pool(tgt_dir)
    src_pool = src_auth.get("credential_pool", {})
    tgt_pool = tgt_auth.get("credential_pool", {})

    src_env = read_env_file(src_dir / ".env")
    tgt_env_path = tgt_dir / ".env"

    for provider, creds in src_pool.items():
        existing_tokens = {
            c.get("access_token") or c.get("api_key")
            for c in tgt_pool.get(provider, [])
        }
        for cred in creds:
            auth_type = cred.get("auth_type")
            source_tag = cred.get("source", "")
            label = cred.get("label", provider)

            if source_tag == "gh_cli" or (auth_type == "oauth" and not include_oauth):
                continue

            if source_tag.startswith("env:"):
                var_name = source_tag.split(":", 1)[1]
                value = src_env.get(var_name)
                if value is None:
                    continue
                write_env_var(tgt_env_path, var_name, value)
                continue

            token = cred.get("access_token") or cred.get("api_key")
            if not token or token in existing_tokens:
                continue
            cred_type = "oauth" if auth_type == "oauth" else "api-key"
            r = run_hermes(
                target,
                ["auth", "add", provider, "--type", cred_type, "--api-key", token, "--label", f"synced-from-{source or 'default'}"],
            )
            if r.returncode == 0:
                existing_tokens.add(token)


def _sync_default_credentials_into(target_profile_name):
    """Sync model config + credentials from the default profile into a newly-linked profile."""
    sync_model_config(None, target_profile_name)
    sync_credentials(None, target_profile_name, include_oauth=False)


def link_profiles():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    data = load_sources()
    sources = data.get("sources", {})

    for source_name in sources:
        source_dir = NETWORK_DIR / source_name
        if not source_dir.is_dir():
            continue

        for item in source_dir.iterdir():
            if item.is_dir() and item.name != ".git":
                target = PROFILES_DIR / item.name

                if target.is_symlink():
                    target.unlink()
                    shutil.copytree(item, target)
                    console.print(f"  [green]Migrated {item.name} from symlink to copy[/green]")
                elif not target.exists():
                    shutil.copytree(item, target)
                    console.print(f"  [green]Copied {item.name}[/green]")
                else:
                    # Overwrite-copy updates existing files without touching local runtime files.
                    # Note: files removed from source repo are not deleted in target profile.
                    shutil.copytree(item, target, dirs_exist_ok=True)
                    console.print(f"  [dim]Updated {item.name}[/dim]")

                # Generate config.yaml from config.example.yaml FIRST — this
                # establishes the profile's own intended model tier (see
                # model.md) before credential sync runs. sync_model_config()
                # is additive-only (won't override an existing model), but
                # that guard only works if config.yaml — and therefore the
                # tiered model — already exists by the time it checks.
                config_example = target / "config.example.yaml"
                config = target / "config.yaml"
                if config_example.exists() and not config.exists():
                    try:
                        shutil.copy2(config_example, config)
                        console.print(f"  [dim]Generated default config.yaml for {item.name}[/dim]")
                    except OSError as e:
                        console.print(f"  [yellow]Warning:[/yellow] Failed to generate config.yaml for {item.name}: {e}")

                try:
                    _sync_default_credentials_into(item.name)
                except Exception as e:
                    console.print(f"  [yellow]Warning:[/yellow] Failed to sync credentials for {item.name}: {e}")


@hermes_app.command("install")
def install(
    repo_url: str = typer.Argument(..., help="The Git repository URL containing the agentic network"),
    name: str = typer.Option(None, "--name", help="Name for this source (defaults to the repo URL's basename)"),
):
    """Onboard a team's agentic network."""
    ensure_git()
    _migrate_legacy_single_source()

    source_name = name or _derive_source_name(repo_url)
    NETWORK_DIR.mkdir(parents=True, exist_ok=True)
    source_dir = NETWORK_DIR / source_name

    if source_dir.exists():
        if (source_dir / ".git").exists():
            console.print(
                f"[yellow]Source '{source_name}' already exists at {source_dir}. "
                "Use 'valstorm hermes sync' to update it.[/yellow]"
            )
            raise typer.Exit(1)
        else:
            console.print(
                f"[yellow]Warning:[/yellow] Source '{source_name}' exists but is missing/corrupt (no .git found). "
                "Re-cloning..."
            )
            shutil.rmtree(source_dir)

    console.print(f"Cloning {repo_url} into {source_dir}...")
    res = subprocess.run(["git", "clone", repo_url, str(source_dir)], capture_output=True, text=True)
    if res.returncode != 0:
        console.print(f"[bold red]Git clone failed:[/bold red]\n{res.stderr}")
        if source_dir.exists():
            shutil.rmtree(source_dir)
        raise typer.Exit(1)

    data = load_sources()
    data.setdefault("sources", {})[source_name] = {"repo_url": repo_url}
    save_sources(data)

    console.print("Copying profiles...")
    link_profiles()
    console.print("\n[bold green]Network installed successfully![/bold green]")
    console.print("Run `hermes --profile <profile_name>` to begin.")


@hermes_app.command("sync")
def sync():
    """Keep the team's agentic network up to date."""
    ensure_git()
    _migrate_legacy_single_source()

    data = load_sources()
    sources = data.get("sources", {})

    if not sources:
        console.print("[bold red]No sources installed. Run 'valstorm hermes install <repo-url>' first.[/bold red]")
        raise typer.Exit(1)

    any_failed = False
    for source_name in sources:
        source_dir = NETWORK_DIR / source_name
        if not (source_dir / ".git").exists():
            console.print(f"[yellow]Skipping '{source_name}':[/yellow] not found or missing .git at {source_dir}.")
            any_failed = True
            continue

        console.print(f"Pulling latest updates for '{source_name}'...")
        res = subprocess.run(["git", "-C", str(source_dir), "pull"], capture_output=True, text=True)
        if res.returncode != 0:
            console.print(f"[bold red]Git pull failed for '{source_name}':[/bold red]\n{res.stderr}")
            any_failed = True
            continue

        console.print(f"  [dim]{res.stdout.strip()}[/dim]")

    console.print("Updating profiles...")
    link_profiles()

    if any_failed:
        console.print("\n[yellow]Network synced with some errors (see above).[/yellow]")
    else:
        console.print("\n[bold green]Network synced successfully![/bold green]")

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/main.py

```python
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
from .vfs_cmds import vfs_app
from .hermes_cmds import hermes_app

app.add_typer(sandbox_app, name="sandbox")
app.add_typer(record_app, name="record")
app.add_typer(schema_app, name="schema")
app.add_typer(vfs_app, name="vfs")
app.add_typer(hermes_app, name="hermes")
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
    Update the Valstorm CLI to the latest version.
    """
    from importlib.metadata import version, PackageNotFoundError
    try:
        current_version = version("valstorm-cli")
    except PackageNotFoundError:
        current_version = "unknown"

    console.print(f"Current version: [cyan]{current_version}[/cyan]")
    repo_url = "git+https://github.com/Valstorm-Corp/monorepo.git#subdirectory=cli"
    
    try:
        with console.status("[bold cyan]Updating Valstorm CLI...[/bold cyan]") as status:
            is_installed = "site-packages" in __file__

            # Check if we are running inside the monorepo source tree itself
            if not is_installed:
                try:
                    root = get_project_root()
                    if (root / "cli" / "pyproject.toml").exists():
                        status.update("[bold cyan]Detected local monorepo. Running uv sync...[/bold cyan]")
                        if shutil.which("uv"):
                            subprocess.run(["uv", "sync", "--project", str(root / "cli")], check=True, capture_output=True)
                            console.print("[bold green]✓[/bold green] Local workspace synced successfully.")
                            return
                except Exception:
                    pass

            # Check if installed as a uv tool first
            if shutil.which("uv") and "uv/tools" in sys.executable:
                status.update("[bold cyan]Detected installation as a uv tool. Upgrading...[/bold cyan]")
                subprocess.run(["uv", "tool", "upgrade", "valstorm-cli"], check=True, capture_output=True)
                console.print("[bold green]✓[/bold green] Valstorm CLI uv tool updated successfully.")
                return

            # Fallback to pip upgrade
            if shutil.which("uv"):
                status.update("[bold cyan]Using uv pip to upgrade from GitHub...[/bold cyan]")
                cmd = ["uv", "pip", "install", "--upgrade", repo_url]
            else:
                status.update("[bold cyan]Using pip to upgrade from GitHub...[/bold cyan]")
                cmd = [sys.executable, "-m", "pip", "install", "--upgrade", repo_url]
                 
            subprocess.run(cmd, check=True, capture_output=True)
            
        console.print("[bold green]✓[/bold green] Valstorm CLI updated successfully.")
        
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error during update:[/bold red] Command failed with exit code {e.returncode}")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode('utf-8', errors='ignore')}[/dim]")
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
        "manifest": "manifest.json",
        "objects": [
            "record_trigger", "function", "automation", "ai_agent", "app", 
            "app_page", "app_metadata", "permission", 
            "notification_setting", "schedule_trigger_setting", "workspace"
        ]
    }
    
    with open(target_path / "valstorm.json", "w") as f:
        json.dump(config, f, indent=4)

    # 1.0.1 Create default manifest.json
    default_manifest = {
        "version": "1.0",
        "description": "Default deployment manifest",
        "objects": {
            "record_trigger": "*",
            "function": "*",
            "automation": "*",
            "ai_agent": "*",
            "app": "*",
            "app_page": "*",
            "app_metadata": "*",
            "permission": "*",
            "notification_setting": "*",
            "schedule_trigger_setting": "*",
            "workspace": "*"
        }
    }
    with open(target_path / "manifest.json", "w") as f:
        json.dump(default_manifest, f, indent=4)

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

def version_callback(value: bool):
    if value:
        try:
            from importlib.metadata import version
            __version__ = version("valstorm-cli")
        except Exception:
            data = open(Path(__file__).parent.parent.parent / "pyproject.toml", "r").read()
            version_line = next((line for line in data.splitlines() if line.strip().startswith("version =")), None)
            __version__ = version_line.split("=")[1].strip().strip('"') if version_line else "Unknown"
        console.print(f"Valstorm CLI version: [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit()

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit."
    )
):
    """
    Valstorm Developer CLI.
    """
    pass

deploy_app = typer.Typer(help="Manage deployments.")
deploy_app_group = typer.Typer(help="Manage App deployments.")
deploy_app.add_typer(deploy_app_group, name="app")
app.add_typer(deploy_app, name="deploy")

@deploy_app.command(name="manifest")
def deploy_manifest_command(
    manifest_path: str = typer.Argument(..., help="Path to the deployment manifest JSON file."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate manifest assets without deploying them.")
):
    """
    Deploy specific metadata assets defined in a manifest file to any environment.
    """
    import json
    from pathlib import Path
    
    path = Path(manifest_path)
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest file not found: {manifest_path}")
        raise typer.Exit(1)
        
    try:
        with open(path, "r") as f:
            manifest_data = json.load(f)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to parse manifest JSON: {e}")
        raise typer.Exit(1)
        
    console.print(f"Deploying manifest [cyan]{manifest_path}[/cyan]...")
    
    if dry_run:
        console.print("[yellow]Dry Run Mode Enabled: Validating local manifest contents...[/yellow]")
        from rich.table import Table
        table = Table(title="Assets Checked (Ready for Deployment)")
        table.add_column("Type", style="cyan")
        table.add_column("Asset", style="green")
        table.add_column("Status", style="yellow")
        
        objects = manifest_data.get("objects", {})
        schemas = manifest_data.get("schemas", [])
        
        for file_type, files in objects.items():
            for f_name in files:
                # check if file exists under object/{file_type}/{f_name}
                local_f = Path("object") / file_type / f_name
                # Check for companion code/meta files
                if local_f.exists():
                    status_str = "Found (Local)"
                else:
                    status_str = "Not Found Locally (Will be skipped or queried)"
                table.add_row(file_type, f_name, status_str)
                
        for s_name in schemas:
            local_s = Path("schemas") / f"{s_name}.json"
            if local_s.exists():
                status_str = "Found (Local)"
            else:
                status_str = "Not Found Locally (Will be skipped)"
            table.add_row("schema", s_name, status_str)
            
        console.print(table)
        console.print("[green]✓ Validation passed. Ready to deploy.[/green]")
        return
        
    # Delegate to the metadata sync push engine
    from .sync import push
    try:
        push(manifest=str(path), profile=profile, env=env)
    except Exception as e:
        console.print(f"[bold red]Deployment failed:[/bold red] {e}")
        raise typer.Exit(1)

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


@deploy_app_group.command(name="local")
def deploy_app_local(
    app_config: str = typer.Option("app.json", "--config", "-c", help="Path to app.json configuration."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Compile and deploy an application from local source files directly to the target environment.
    """
    from pathlib import Path
    from .bundler import bundle_local_app
    
    try:
        root = get_project_root()
    except Exception:
        console.print("[bold red]Error:[/bold red] Must be run inside a Valstorm project.")
        raise typer.Exit(1)
        
    config_path = root / app_config
    if not config_path.exists():
        console.print(f"[bold red]Error:[/bold red] Application config not found at: {app_config}")
        raise typer.Exit(1)
        
    auth = get_auth(profile=profile, env=env, use_parent=True)
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    api_base_url = get_api_base_url(env=env)
    
    console.print(f"Assembling local app bundle from [cyan]{app_config}[/cyan]...")
    try:
        app_bundle = bundle_local_app(config_path, root)
    except Exception as e:
        console.print(f"[bold red]Failed to assemble app bundle:[/bold red] {e}")
        raise typer.Exit(1)
        
    console.print(f"Deploying app [green]{app_bundle['name']}[/green] ([dim]{app_bundle['id']}[/dim]) directly to environment [blue]{get_api_base_url(auth.env)}[/blue]...")
    
    # PUT the compiled bundle to `/apps/deploy` as expected by receive_app_deploy
    url = f"{api_base_url}/apps/deploy"
    
    try:
        response = httpx.put(
            url,
            json=app_bundle,
            headers={"Authorization": f"Bearer {auth.access_token}"},
            timeout=180.0
        )
        if response.status_code == 200:
            console.print("[bold green]✓ Local application deployed successfully![/bold green]")
            try:
                from rich.json import JSON
                console.print(JSON.from_data(response.json()))
            except Exception:
                console.print(response.text)
        else:
            console.print(f"[bold red]Deployment failed ({response.status_code}):[/bold red] {response.text}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error connecting to API:[/bold red] {str(e)}")
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
    
    target_val = target
    if not target_val:
        try:
            if auth.auth_file.exists():
                import json
                auth_data = json.loads(auth.auth_file.read_text())
                target_val = auth_data.get("user", {}).get("organization_id", "").split('_s_')[0]
        except Exception:
            pass
            
        if not target_val:
            try:
                response = httpx.get(
                    f"{api_base_url}/auth/load",
                    headers={"Authorization": f"Bearer {auth.access_token}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    target_val = response.json().get("user", {}).get("organization_id", "").split('_s_')[0]
            except Exception:
                pass
                
    if not target_val:
        console.print("[bold red]Error:[/bold red] Could not determine target parent organization. Please specify '--target' explicitly.")
        raise typer.Exit(1)
        
    try:
        # Execute POST Push
        url = f"{api_base_url}/sandbox/{sandbox_name}/app/{app_name}/push/{target_val}"
        if target:
            console.print(f"Pushing app [blue]{app_name}[/blue] from sandbox [blue]{sandbox_name}[/blue] to target [green]{target}[/green]...")
        else:
            console.print(f"Pushing app [blue]{app_name}[/blue] from sandbox [blue]{sandbox_name}[/blue] to parent environment [green]{target_val}[/green]...")
            
        response = httpx.post(
            url, 
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


@manifest_app.command(name="diff")
def manifest_diff(
    ref: Optional[str] = typer.Argument(None, help="Git reference (branch, commit, etc.) to diff against. If omitted, diffs uncommitted changes."),
    output: str = typer.Option("manifests/diff_deployment.json", "--output", "-o", help="Target output manifest file path."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing manifest without asking.")
):
    """
    Generate a deployment manifest from local git differences (committed or uncommitted).
    """
    try:
        from .git_utils import get_git_diff_files, get_git_root
        from .manifest_builder import build_manifest_from_files
    except ImportError as e:
        console.print(f"[bold red]Failed to import manifest builders:[/bold red] {e}")
        raise typer.Exit(1)
        
    try:
        root = get_git_root()
        files = get_git_diff_files(ref)
    except Exception as e:
        console.print(f"[bold red]Git Error:[/bold red] {e}")
        raise typer.Exit(1)
        
    if not files:
        console.print("[yellow]No local changes detected. Manifest will be empty.[/yellow]")
        raise typer.Exit(0)
        
    manifest = build_manifest_from_files(files, root)
    
    out_path = root / output
    out_path.parent.mkdir(exist_ok=True)
    
    if out_path.exists() and not force:
        if not typer.confirm(f"Manifest at {output} already exists. Overwrite?"):
            raise typer.Exit(0)
            
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=4)
        
    console.print(f"[bold green]✓ Manifest generated successfully![/bold green] Saved to: [cyan]{output}[/cyan]")
    
    # Render table of identified items
    from rich.table import Table
    table = Table(title="Identified Deployment Assets")
    table.add_column("Type", style="cyan")
    table.add_column("Asset Name", style="green")
    
    has_assets = False
    for obj_type, assets in manifest.get("objects", {}).items():
        for asset in assets:
            table.add_row(obj_type, asset)
            has_assets = True
            
    for schema in manifest.get("schemas", []):
        table.add_row("schema", schema)
        has_assets = True
        
    if has_assets:
        console.print(table)
    else:
        console.print("[yellow]No Valstorm metadata objects or schemas identified in the changes.[/yellow]")




```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/manifest_builder.py

```python
from pathlib import Path
from typing import Set, Dict, Any

def build_manifest_from_files(files: Set[Path], root_dir: Path) -> Dict[str, Any]:
    """
    Scans a set of files and maps them to Valstorm metadata object types
    or database schemas. Builds a valid manifest data structure.
    """
    manifest = {
        "version": "1.0",
        "description": "Git diff generated deployment manifest",
        "objects": {},
        "schemas": []
    }
    
    for file_path in files:
        try:
            rel_path = file_path.relative_to(root_dir)
        except ValueError:
            continue  # The file is not under the workspace root directory
            
        parts = rel_path.parts
        if not parts:
            continue
            
        # 1. Match Schemas (saved under <workspace>/schemas/<schema_name>.json)
        if parts[0] == "schemas" and file_path.suffix == ".json":
            manifest["schemas"].append(file_path.stem)
            
        # 2. Match Object Files (saved under <workspace>/object/<object_type>/<file_name>)
        elif parts[0] == "object" and len(parts) >= 3:
            obj_type = parts[1]
            file_name = parts[2]
            
            # We care about actual files (code, JSON metadata, or template files)
            if file_path.is_file() or file_path.suffix in (".py", ".json", ".yaml", ".yml", ".md", ".html"):
                stem_name = file_path.stem
                
                # Exclude monolithic legacy metadata JSON or any summary/config file
                if file_name == f"{obj_type}_metadata.json":
                    continue
                # Exclude individual companion metadata JSONs from being listed twice in code lists
                # Usually we want function and record_trigger listings to point to the code .py filename,
                # while other object types might point directly to .json metadata filenames.
                if obj_type in ("function", "record_trigger"):
                    target_name = f"{stem_name}.py"
                else:
                    # For other types (e.g. workspace, permission, app, ai_agent), target the specific file name
                    target_name = file_name
                
                # Check for companion metadata JSON filenames that end with `{stem_name}_{id}.json`
                # If it's a companion metadata JSON file for a python file, normalize it to the python file
                if obj_type in ("function", "record_trigger") and file_path.suffix == ".json":
                    # If there's an underscore, it might be {name}_{uuid}.json
                    if "_" in stem_name:
                        parts_of_stem = stem_name.rsplit("_", 1)
                        # If the last segment looks like an ID, use the first segment
                        if len(parts_of_stem) == 2 and any(c.isdigit() for c in parts_of_stem[1]):
                            target_name = f"{parts_of_stem[0]}.py"
                        else:
                            target_name = f"{stem_name}.py"
                    else:
                        target_name = f"{stem_name}.py"
                        
                if obj_type not in manifest["objects"]:
                    manifest["objects"][obj_type] = []
                    
                if target_name not in manifest["objects"][obj_type]:
                    manifest["objects"][obj_type].append(target_name)
                    
    # Clean up empty properties
    if not manifest["schemas"]:
        manifest.pop("schemas")
    if not manifest["objects"]:
        manifest["objects"] = {}
        
    return manifest

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/project.py

```python
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


```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/query.py

```python
import typer
import httpx
import json
import csv
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from .auth import ValstormAuth

console = Console()
query_app = typer.Typer(help="Execute Queries", no_args_is_help=True)

def handle_query_save_and_output(data, output: str, save: Optional[str], csv_file: Optional[str]):
    if save:
        with open(save, 'w') as f:
            json.dump(data, f, indent=4)
        console.print(f"[green]✓ Results saved to {save}[/green]")
        
    if csv_file:
        if isinstance(data, list) and len(data) > 0:
            keys = data[0].keys()
            with open(csv_file, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(data)
            console.print(f"[green]✓ Results saved to {csv_file}[/green]")
        elif isinstance(data, dict):
            keys = data.keys()
            with open(csv_file, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerow(data)
            console.print(f"[green]✓ Results saved to {csv_file}[/green]")
        else:
            console.print("[yellow]Cannot save non-list/dict data as CSV.[/yellow]")

    if output == "json":
        console.print_json(data=data)
    else:
        if not data:
            console.print("[yellow]No records found.[/yellow]")
            return
        
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
            columns = data.keys()
            for col in columns:
                table.add_column(col)
            table.add_row(*[str(data.get(col, "")) for col in columns])
            console.print(table)
        else:
            console.print(data)

def get_query_string(query: Optional[str], file: Optional[str]) -> str:
    if file:
        try:
            with open(file, 'r') as f:
                return f.read().strip()
        except Exception as e:
            console.print(f"[bold red]Failed to read query file:[/bold red] {e}")
            raise typer.Exit(1)
    elif query:
        return query
    else:
        console.print("[bold red]Must provide either a query string or --file.[/bold red]")
        raise typer.Exit(1)

def save_query_to_file(query_str: str, file_path: str):
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(query_str)
        console.print(f"[green]✓ Query saved to {file_path}[/green]")
    except Exception as e:
        console.print(f"[bold red]Failed to save query file:[/bold red] {e}")

@query_app.command(name="sql")
def sql(
    query: Optional[str] = typer.Argument(None, help="The SQL query to execute."),
    file: Optional[str] = typer.Option(None, "--file", help="Execute query from file."),
    save_query: Optional[str] = typer.Option(None, "--save-query", help="Save the query itself to a file."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    output: str = typer.Option("table", "--output", "-o", help="Output format (table, json)."),
    bypass_cache: bool = typer.Option(False, "--bypass-cache", help="Bypass the query cache."),
    save: Optional[str] = typer.Option(None, "--save", "-s", help="Save results to a JSON file."),
    csv_file: Optional[str] = typer.Option(None, "--csv", help="Save results to a CSV file.")
):
    """Execute a SQL-like query against the Valstorm API."""
    query_str = get_query_string(query, file)
    
    if save_query:
        save_query_to_file(query_str, save_query)
        
    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        try:
            response = client.post("/query", json={
                "query": query_str,
                "bypass_cache": bypass_cache
            })
            
            if response.status_code != 200:
                console.print(f"[bold red]Query failed ({response.status_code}):[/bold red] {response.text}")
                raise typer.Exit(1)
                
            data = response.json()
            handle_query_save_and_output(data, output, save, csv_file)
                    
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@query_app.command(name="graphql")
def graphql(
    query: Optional[str] = typer.Argument(None, help="The GraphQL query to execute."),
    file: Optional[str] = typer.Option(None, "--file", help="Execute query from file."),
    save_query: Optional[str] = typer.Option(None, "--save-query", help="Save the query itself to a file."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    output: str = typer.Option("json", "--output", "-o", help="Output format (table, json)."),
    save: Optional[str] = typer.Option(None, "--save", "-s", help="Save results to a JSON file."),
    csv_file: Optional[str] = typer.Option(None, "--csv", help="Save results to a CSV file.")
):
    """Execute a GraphQL query against the Valstorm API."""
    query_str = get_query_string(query, file)
    
    if save_query:
        save_query_to_file(query_str, save_query)
        
    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        try:
            response = client.post("/graphql", json={
                "query": query_str
            })
            
            if response.status_code != 200:
                console.print(f"[bold red]GraphQL Query failed ({response.status_code}):[/bold red] {response.text}")
                raise typer.Exit(1)
                
            data = response.json()
            handle_query_save_and_output(data, output, save, csv_file)
                    
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/record.py

```python
import typer
import httpx
import json
from typing import Optional, List
from rich.console import Console
from .auth import ValstormAuth

console = Console()
record_app = typer.Typer(help="Manage records", no_args_is_help=True)

def load_data(data: Optional[str], file: Optional[str]) -> List[dict]:
    if file:
        try:
            with open(file, 'r') as f:
                content = json.load(f)
                return content if isinstance(content, list) else [content]
        except Exception as e:
            console.print(f"[bold red]Failed to read file:[/bold red] {e}")
            raise typer.Exit(1)
    elif data:
        try:
            content = json.loads(data)
            return content if isinstance(content, list) else [content]
        except Exception as e:
            console.print(f"[bold red]Failed to parse data JSON:[/bold red] {e}")
            raise typer.Exit(1)
    else:
        console.print("[bold red]Must provide either --data or --file.[/bold red]")
        raise typer.Exit(1)

@record_app.command(name="create")
def create_record(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema/object."),
    data: Optional[str] = typer.Option(None, "--data", help="JSON string of record data."),
    file: Optional[str] = typer.Option(None, "--file", help="JSON file containing record data."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Create one or multiple records."""
    payload = load_data(data, file)
    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.post(f"/object/{schema_api_name}", json=payload)
            if res.status_code not in (200, 201):
                console.print(f"[bold red]Failed to create record(s):[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print("[green]✓ Successfully created record(s).[/green]")
            console.print_json(data=res.json())
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@record_app.command(name="update")
def update_record(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema/object."),
    data: Optional[str] = typer.Option(None, "--data", help="JSON string of update data (must include 'id')."),
    file: Optional[str] = typer.Option(None, "--file", help="JSON file containing update data."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Update existing records."""
    payload = load_data(data, file)
    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.patch(f"/object/{schema_api_name}", json=payload)
            if res.status_code != 200:
                console.print(f"[bold red]Failed to update record(s):[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print("[green]✓ Successfully updated record(s).[/green]")
            console.print_json(data=res.json())
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@record_app.command(name="delete")
def delete_record(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema/object."),
    id: Optional[List[str]] = typer.Option(None, "--id", help="Record ID to delete (can be specified multiple times)."),
    file: Optional[str] = typer.Option(None, "--file", help="JSON file containing array of IDs."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Delete records."""
    ids_to_delete = []
    if file:
        try:
            with open(file, 'r') as f:
                content = json.load(f)
                ids_to_delete = content if isinstance(content, list) else [content]
        except Exception as e:
            console.print(f"[bold red]Failed to read file:[/bold red] {e}")
            raise typer.Exit(1)
    elif id:
        ids_to_delete = id
    else:
        console.print("[bold red]Must provide either --id or --file.[/bold red]")
        raise typer.Exit(1)

    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.request("DELETE", f"/object/{schema_api_name}", params={"ids": ids_to_delete})
            if res.status_code != 200:
                console.print(f"[bold red]Failed to delete record(s):[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print(f"[green]✓ Successfully deleted {len(ids_to_delete)} record(s).[/green]")
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/sandbox.py

```python
import typer
import httpx
from typing import Optional, List
from rich.console import Console
from .auth import ValstormAuth, get_api_base_url

console = Console()
sandbox_app = typer.Typer(help="Manage developer sandboxes.")

users_app = typer.Typer(help="Manage users in a sandbox.")
sandbox_app.add_typer(users_app, name="users")

def _get_auth() -> ValstormAuth:
    auth = ValstormAuth(use_parent=True)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not authenticated or failed to refresh.[/bold red] Run 'valstorm login' first.")
        raise typer.Exit(1)
    return auth

@sandbox_app.command("create")
def create_sandbox(
    name: str = typer.Argument(..., help="Lowercase alphanumeric name for the sandbox (e.g., 'dev')."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Markdown description for the sandbox.")
):
    """Provisions a new sandbox database and copies configuration."""
    auth = _get_auth()
    base_url = get_api_base_url()
    
    payload = {"name": name}
    if description:
        payload["description"] = description
        
    console.print(f"Creating sandbox [bold cyan]{name}[/bold cyan]...")
    try:
        response = httpx.post(
            f"{base_url}/sandbox",
            json=payload,
            headers={"Authorization": f"Bearer {auth.access_token}"},
            timeout=120.0
        )
        response.raise_for_status()
        data = response.json()
        console.print(f"[bold green]✓ Sandbox '{name}' created successfully![/bold green]")
        console.print(f"ID: [yellow]{data.get('id')}[/yellow]")
    except httpx.HTTPStatusError as e:
        console.print(f"[bold red]Error ({e.response.status_code}):[/bold red] {e.response.text}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to create sandbox:[/bold red] {str(e)}")
        raise typer.Exit(1)

@sandbox_app.command("list")
def list_sandboxes():
    """Lists all sandbox environments associated with the active production organization."""
    auth = _get_auth()
    base_url = get_api_base_url()
    
    console.print("Fetching sandboxes...")
    try:
        response = httpx.get(
            f"{base_url}/sandbox",
            headers={"Authorization": f"Bearer {auth.access_token}"},
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        
        if not data:
            console.print("No sandboxes found.")
            return
            
        from rich.table import Table
        table = Table(title="Developer Sandboxes")
        table.add_column("Sandbox Name", style="cyan")
        table.add_column("ID", style="yellow")
        table.add_column("Description")
        
        for sb in data:
            table.add_row(sb.get("sandbox_name", ""), sb.get("id", ""), sb.get("description", "") or "")
            
        console.print(table)
    except httpx.HTTPStatusError as e:
        console.print(f"[bold red]Error ({e.response.status_code}):[/bold red] {e.response.text}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to list sandboxes:[/bold red] {str(e)}")
        raise typer.Exit(1)

@sandbox_app.command("refresh")
def refresh_sandbox(name: str = typer.Argument(..., help="Sandbox name to refresh (e.g., 'dev')")):
    """Wipes the sandbox database and re-clones configuration from production."""
    auth = _get_auth()
    base_url = get_api_base_url()
    
    console.print(f"Refreshing sandbox [bold cyan]{name}[/bold cyan]... (This may take a minute)")
    try:
        response = httpx.post(
            f"{base_url}/sandbox/{name}/refresh",
            headers={"Authorization": f"Bearer {auth.access_token}"},
            timeout=180.0
        )
        response.raise_for_status()
        console.print(f"[bold green]✓ Sandbox '{name}' refreshed successfully![/bold green]")
    except httpx.HTTPStatusError as e:
        console.print(f"[bold red]Error ({e.response.status_code}):[/bold red] {e.response.text}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to refresh sandbox:[/bold red] {str(e)}")
        raise typer.Exit(1)

@sandbox_app.command("delete")
def delete_sandbox(
    name: str = typer.Argument(..., help="Sandbox name to delete (e.g., 'dev')"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without prompting.")
):
    """Permanently deletes a sandbox and all its contents."""
    auth = _get_auth()
    base_url = get_api_base_url()
    
    if not force:
        confirm = typer.confirm(f"Are you sure you want to permanently delete the sandbox '{name}'?")
        if not confirm:
            console.print("Operation cancelled.")
            raise typer.Exit()
            
    console.print(f"Deleting sandbox [bold cyan]{name}[/bold cyan]...")
    try:
        response = httpx.delete(
            f"{base_url}/sandbox/{name}",
            headers={"Authorization": f"Bearer {auth.access_token}"},
            timeout=120.0
        )
        response.raise_for_status()
        console.print(f"[bold green]✓ Sandbox '{name}' deleted successfully![/bold green]")
    except httpx.HTTPStatusError as e:
        console.print(f"[bold red]Error ({e.response.status_code}):[/bold red] {e.response.text}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to delete sandbox:[/bold red] {str(e)}")
        raise typer.Exit(1)

@users_app.command("add")
def add_users(
    name: str = typer.Argument(..., help="Sandbox name"),
    users: List[str] = typer.Argument(..., help="List of User IDs or Emails to add")
):
    """Add users to a sandbox environment."""
    auth = _get_auth()
    base_url = get_api_base_url()
    
    console.print(f"Adding users to sandbox [bold cyan]{name}[/bold cyan]...")
    try:
        response = httpx.post(
            f"{base_url}/sandbox/{name}/users",
            json={"users": users},
            headers={"Authorization": f"Bearer {auth.access_token}"},
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        added = data.get("added_users", [])
        for u in added:
            console.print(f"  [green]+[/green] {u}")
        console.print(f"[bold green]✓ Added {len(added)} users.[/bold green]")
    except httpx.HTTPStatusError as e:
        console.print(f"[bold red]Error ({e.response.status_code}):[/bold red] {e.response.text}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to add users:[/bold red] {str(e)}")
        raise typer.Exit(1)

@users_app.command("remove")
def remove_users(
    name: str = typer.Argument(..., help="Sandbox name"),
    users: List[str] = typer.Argument(..., help="List of User IDs or Emails to remove")
):
    """Remove users from a sandbox environment."""
    auth = _get_auth()
    base_url = get_api_base_url()
    
    console.print(f"Removing users from sandbox [bold cyan]{name}[/bold cyan]...")
    try:
        # httpx.request is used because delete method with body isn't supported directly via client.delete
        response = httpx.request(
            method="DELETE",
            url=f"{base_url}/sandbox/{name}/users",
            json={"users": users},
            headers={"Authorization": f"Bearer {auth.access_token}"},
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        removed = data.get("removed_users", [])
        for u in removed:
            console.print(f"  [red]-[/red] {u}")
        console.print(f"[bold green]✓ Removed {len(removed)} users.[/bold green]")
    except httpx.HTTPStatusError as e:
        console.print(f"[bold red]Error ({e.response.status_code}):[/bold red] {e.response.text}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to remove users:[/bold red] {str(e)}")
        raise typer.Exit(1)


@sandbox_app.command("use")
def use_sandbox(
    name: str = typer.Argument(..., help="The name of the sandbox to switch to.")
):
    """
    Switch the local workspace target to a specific sandbox.
    """
    from .auth import get_project_root, load_config
    import json
    
    try:
        root = get_project_root()
    except Exception:
        console.print("[bold red]Not in a Valstorm project directory.[/bold red]")
        raise typer.Exit(1)
        
    config = load_config(root)
    
    # Optional: Verify sandbox actually exists in parent org by listing them
    auth = _get_auth() # uses use_parent=True internally
    base_url = get_api_base_url()
    try:
        res = httpx.get(
            f"{base_url}/sandbox",
            headers={"Authorization": f"Bearer {auth.access_token}"},
            timeout=10.0
        )
        if res.status_code == 200:
            sandboxes = res.json()
            sandbox_names = [s.get("sandbox_name") for s in sandboxes if s.get("sandbox_name")]
            if name not in sandbox_names:
                console.print(f"[yellow]Warning: Sandbox '{name}' was not found in your organization.[/yellow]")
                console.print(f"Available sandboxes: {', '.join(sandbox_names) or 'None'}")
                if not typer.confirm("Do you want to switch to it anyway?"):
                    raise typer.Exit(0)
    except Exception:
        pass # Handle gracefully if offline or request fails
        
    config["sandbox"] = name
    
    with open(root / "valstorm.json", "w") as f:
        json.dump(config, f, indent=4)
        
    console.print(f"[bold green]✓ Switched workspace target to sandbox '{name}'[/bold green]")


@sandbox_app.command("switch", hidden=True)
def switch_sandbox(
    name: str = typer.Argument(..., help="The name of the sandbox to switch to.")
):
    """
    Alias for use.
    """
    use_sandbox(name)


@sandbox_app.command("use-parent")
def use_parent():
    """
    Switch the local workspace target back to the parent production/dev organization.
    """
    from .auth import get_project_root, load_config
    import json
    
    try:
        root = get_project_root()
    except Exception:
        console.print("[bold red]Not in a Valstorm project directory.[/bold red]")
        raise typer.Exit(1)
        
    config = load_config(root)
    if "sandbox" in config:
        del config["sandbox"]
        
    with open(root / "valstorm.json", "w") as f:
        json.dump(config, f, indent=4)
        
    console.print("[bold green]✓ Switched workspace target back to parent production/dev environment[/bold green]")


@sandbox_app.command("switch-back", hidden=True)
def switch_back():
    """
    Alias for use-parent.
    """
    use_parent()


```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/scaffold_cmds.py

```python
import typer
import json
from typing import Optional
from pathlib import Path
from rich.console import Console
from .scaffold import run_web_scaffolding
from .auth import get_auth, get_project_root

console = Console()
scaffold_app = typer.Typer(help="Generate local files from Valstorm records.")





@scaffold_app.command(name="web")
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

@scaffold_app.command(name="docs")
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





```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/scaffold.py

```python
import json
import uuid
from pathlib import Path

def extract_rich_text_values(node):
    """
    Recursively searches the node tree to find all RichText values in order.
    """
    if not isinstance(node, dict):
        return []
    
    values = []
    props = node.get("props", {})
    if isinstance(props, dict):
        if props.get("component_type") == "RichText" and "value" in props:
            val = props["value"]
            if val:
                values.append(val)
                
    # Recurse children
    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            values.extend(extract_rich_text_values(child))
            
    return values

def format_frontmatter(metadata):
    """
    Formats metadata dictionary as YAML frontmatter.
    """
    lines = ["---"]
    for k, v in metadata.items():
        if v is not None:
            # Safely encode values as JSON string for YAML compatibility
            val_str = json.dumps(v, ensure_ascii=False)
            lines.append(f"{k}: {val_str}")
    lines.append("---")
    return "\n".join(lines)

def parse_frontmatter(content):
    """
    Parses simple YAML frontmatter.
    Returns: (metadata_dict, body_text)
    """
    if not content.startswith("---"):
        return {}, content
    
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
        
    yaml_text = parts[1]
    body_text = parts[2].strip()
    
    metadata = {}
    for line in yaml_text.strip().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        try:
            # Try to load as JSON to decode quotes/escapes
            metadata[k] = json.loads(v)
        except Exception:
            # Fallback to string stripping
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            metadata[k] = v
    return metadata, body_text

def _update_rich_text_in_tree(node, new_value):
    """
    Recursively searches the tree to find and update the first RichText component's value.
    Returns True if updated, False otherwise.
    """
    if not isinstance(node, dict):
        return False
    
    props = node.setdefault("props", {})
    if props.get("component_type") == "RichText":
        props["value"] = new_value
        return True
        
    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            if _update_rich_text_in_tree(child, new_value):
                return True
    return False

def _add_rich_text_to_tree(data_list, new_value):
    """
    Adds a new RichText component to the main dropzone of the data list.
    """
    new_id = str(uuid.uuid4())
    rich_text_node = {
        "id": new_id,
        "children": [],
        "edges": [],
        "parent": "main-dropzone",
        "props": {
            "api_name": "rich_text",
            "value": new_value,
            "class_name": "",
            "category": "HTML",
            "component_type": "RichText",
            "schema_name": "rich_text"
        }
    }
    
    # Find dropzone with id "main-dropzone" or first dropzone
    for node in data_list:
        if isinstance(node, dict):
            props = node.get("props", {})
            if props.get("id") == "main-dropzone" or props.get("component_type") == "DropZone":
                node.setdefault("children", []).append(rich_text_node)
                return True
                
    # Fallback: create dropzone and append rich text
    main_dropzone = {
        "id": 1,
        "children": [rich_text_node],
        "edges": [],
        "parent": None,
        "props": {
            "api_name": "dropzone",
            "class_name": "min-h-[100px] flex flex-col p-1 gap-4",
            "category": "Drag & Drop",
            "component_type": "DropZone",
            "schema_name": "dropzone",
            "paper": False,
            "children": [],
            "id": "main-dropzone",
            "name": "Main Dropzone"
        }
    }
    data_list.append(main_dropzone)
    return True

def run_web_scaffolding(root_path: Path, output_base_dir: Path, progress_callback=None):
    """
    Core scaffolding service logic.
    Calls progress_callback for each scaffolded or skipped file.
    Returns: (total_records, scaffolded_count, skipped_count, tag_counts)
    """
    metadata_path = root_path / "object" / "app_page" / "app_page_metadata.json"
    
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found at {metadata_path}")
        
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
    except Exception as e:
        raise ValueError(f"Error parsing JSON from {metadata_path}: {e}")
        
    scaffolded_count = 0
    skipped_count = 0
    tag_counts = {}
    
    for record in records:
        rec_type = record.get("type")
        rec_tag = record.get("tag")
        
        # Filter for type == "Web Page" and tag in ["Docs", "Marketing"] (case-insensitive)
        if rec_type != "Web Page":
            continue
            
        if not rec_tag or not isinstance(rec_tag, str) or rec_tag.lower() not in ["docs", "marketing"]:
            continue
            
        slug = record.get("slug")
        if not slug:
            if progress_callback:
                progress_callback("skip", record=record, tag=rec_tag)
            skipped_count += 1
            continue
            
        slug = slug.strip("/")
        
        # Extract rich text content
        content_values = []
        data = record.get("data", [])
        if isinstance(data, list):
            for root_node in data:
                content_values.extend(extract_rich_text_values(root_node))
                
        markdown_body = "\n\n".join(content_values) if content_values else ""
        
        # Build metadata for frontmatter
        metadata = {
            "id": record.get("id"),
            "name": record.get("name"),
            "created_date": record.get("created_date"),
            "modified_date": record.get("modified_date"),
            "slug": record.get("slug"),
            "tag": record.get("tag"),
            "seo_title": record.get("seo_title"),
            "seo_description": record.get("seo_description"),
            "seo_keywords": record.get("seo_keywords"),
            "canonical_url": record.get("canonical_url"),
        }
        
        frontmatter = format_frontmatter(metadata)
        
        # Combine frontmatter and markdown body
        file_content = frontmatter
        if markdown_body:
            file_content += f"\n\n{markdown_body}\n"
        else:
            file_content += "\n"
            
        # Target file resolution
        tag_folder = rec_tag.strip() if rec_tag else "Uncategorized"
        target_file_path = output_base_dir / tag_folder / f"{slug}.md"
        parent_dir = target_file_path.parent
        
        parent_dir.mkdir(parents=True, exist_ok=True)
        with open(target_file_path, "w", encoding="utf-8") as out_f:
            out_f.write(file_content)
            
        scaffolded_count += 1
        tag_counts[rec_tag] = tag_counts.get(rec_tag, 0) + 1
        
        if progress_callback:
            progress_callback("scaffold", record=record, tag=rec_tag, tag_folder=tag_folder, slug=slug)
            
    return len(records), scaffolded_count, skipped_count, tag_counts

def prepare_web_push(root_path: Path, output_base_dir: Path):
    """
    Scans output_base_dir for .md files, parses them, and compares with
    object/app_page/app_page_metadata.json.
    Returns: (creates_payload, updates_payload, merged_metadata)
    """
    metadata_path = root_path / "object" / "app_page" / "app_page_metadata.json"
    
    # Load current local metadata state (or empty list if it doesn't exist)
    records = []
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except Exception:
            records = []
            
    # Index records by ID
    records_by_id = {r["id"]: r for r in records if r.get("id")}
    
    creates_payload = []
    updates_payload = []
    
    # Recursively find all .md files in output_base_dir
    md_files = list(output_base_dir.rglob("*.md"))
    
    processed_ids = set()
    
    for file_path in md_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            raise ValueError(f"Error reading local file {file_path}: {e}")
            
        metadata, markdown_body = parse_frontmatter(file_content)
        
        # Determine tag from parent directory if not explicitly in frontmatter
        try:
            rel_parts = file_path.parent.relative_to(output_base_dir).parts
            dir_tag = rel_parts[0] if rel_parts else None
        except Exception:
            dir_tag = None
            
        file_tag = metadata.get("tag") or dir_tag or "Docs"
        
        # Determine slug
        try:
            # Reconstruct slug from relative path to the tag folder
            rel_to_tag = file_path.relative_to(output_base_dir / file_tag)
            # Remove extension
            file_slug = str(rel_to_tag.with_suffix(""))
        except Exception:
            file_slug = metadata.get("slug") or file_path.stem
            
        rec_id = metadata.get("id")
        
        if rec_id and rec_id in records_by_id:
            # We are updating an existing page!
            existing_record = records_by_id[rec_id]
            
            # Update root fields
            existing_record["name"] = metadata.get("name") or existing_record.get("name") or file_path.stem.replace("-", " ").title()
            existing_record["slug"] = file_slug
            existing_record["tag"] = file_tag
            existing_record["seo_title"] = metadata.get("seo_title") or existing_record.get("seo_title")
            existing_record["seo_description"] = metadata.get("seo_description") or existing_record.get("seo_description")
            existing_record["seo_keywords"] = metadata.get("seo_keywords") or existing_record.get("seo_keywords")
            existing_record["canonical_url"] = metadata.get("canonical_url") or existing_record.get("canonical_url")
            existing_record["author_override"] = metadata.get("author_override") or existing_record.get("author_override")
            
            # Ensure data list exists
            data_list = existing_record.get("data", [])
            if not isinstance(data_list, list):
                data_list = []
                existing_record["data"] = data_list
                
            # Update RichText component
            updated_rich_text = False
            for root_node in data_list:
                if _update_rich_text_in_tree(root_node, markdown_body):
                    updated_rich_text = True
                    break
                    
            if not updated_rich_text:
                _add_rich_text_to_tree(data_list, markdown_body)
                
            updates_payload.append(existing_record)
            processed_ids.add(rec_id)
        else:
            # We are creating a brand new page!
            new_id = rec_id or str(uuid.uuid4())
            
            new_record = {
                "id": new_id,
                "name": metadata.get("name") or file_path.stem.replace("-", " ").title(),
                "created_date": None,
                "modified_date": None,
                "created_by": None,
                "modified_by": None,
                "type": "Web Page",
                "description": None,
                "object": None,
                "data": [],
                "slug": file_slug,
                "tag": file_tag,
                "remove_record_page_save_button": False,
                "base_route": "docs" if file_tag.lower() == "docs" else None,
                "icon": None,
                "author_override": metadata.get("author_override"),
                "canonical_url": metadata.get("canonical_url"),
                "seo_description": metadata.get("seo_description"),
                "seo_image": None,
                "seo_keywords": metadata.get("seo_keywords"),
                "seo_title": metadata.get("seo_title"),
                "shared_with": []
            }
            
            _add_rich_text_to_tree(new_record["data"], markdown_body)
            creates_payload.append(new_record)
            processed_ids.add(new_id)
            
    # Combine processed existing records and newly created ones for the final saved local metadata
    merged_metadata = []
    
    # Add all files that were successfully parsed/scaffolded (existing + new)
    for record in updates_payload:
        merged_metadata.append(record)
    for record in creates_payload:
        merged_metadata.append(record)
        
    # Preserve other existing records (e.g. record pages, workspaces)
    for record in records:
        rid = record.get("id")
        if rid and rid not in processed_ids:
            merged_metadata.append(record)
            
    return creates_payload, updates_payload, merged_metadata

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/schema.py

```python
import typer
import httpx
import json
from typing import Optional
from rich.console import Console
from .auth import ValstormAuth

console = Console()
schema_app = typer.Typer(help="Manage schemas / objects", no_args_is_help=True)

@schema_app.command(name="list")
def list_schemas(
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """List all schemas."""
    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.get("/schema")
            if res.status_code != 200:
                console.print(f"[bold red]Failed to list schemas:[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print_json(data=res.json())
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@schema_app.command(name="get")
def get_schema(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema."),
    output: str = typer.Option("json", "--output", "-o", help="Output format."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Get a specific schema definition."""
    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.get(f"/schema/{schema_api_name}")
            if res.status_code != 200:
                console.print(f"[bold red]Failed to get schema:[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print_json(data=res.json())
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@schema_app.command(name="create")
def create_schema(
    name: Optional[str] = typer.Argument(None, help="The display name of the schema."),
    api_name: Optional[str] = typer.Option(None, "--api-name", help="The API name of the schema."),
    file: Optional[str] = typer.Option(None, "--file", help="JSON file containing the schema definition."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Create a new object schema."""
    payload = {}
    if file:
        try:
            with open(file, 'r') as f:
                payload = json.load(f)
        except Exception as e:
            console.print(f"[bold red]Failed to read file:[/bold red] {e}")
            raise typer.Exit(1)
    elif name and api_name:
        payload = {"name": name, "api_name": api_name}
    else:
        console.print("[bold red]Must provide either NAME and --api-name, or --file.[/bold red]")
        raise typer.Exit(1)

    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.post("/schema", json=payload)
            if res.status_code not in (200, 201):
                console.print(f"[bold red]Failed to create schema:[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print("[green]✓ Successfully created schema.[/green]")
            console.print_json(data=res.json())
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@schema_app.command(name="update")
def update_schema(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema."),
    data: str = typer.Option(..., "--data", help="JSON string of schema metadata to update."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Update an existing schema metadata."""
    try:
        payload = json.loads(data)
    except Exception as e:
        console.print(f"[bold red]Failed to parse JSON data:[/bold red] {e}")
        raise typer.Exit(1)

    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.patch(f"/schema/{schema_api_name}", json=payload)
            if res.status_code != 200:
                console.print(f"[bold red]Failed to update schema:[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print("[green]✓ Successfully updated schema.[/green]")
            console.print_json(data=res.json())
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@schema_app.command(name="delete")
def delete_schema(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema."),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """Delete a schema."""
    if not confirm:
        if not typer.confirm(f"Are you sure you want to delete schema '{schema_api_name}'?"):
            raise typer.Exit()

    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    with auth.get_client() as client:
        try:
            res = client.delete(f"/schema/{schema_api_name}")
            if res.status_code != 200:
                console.print(f"[bold red]Failed to delete schema:[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print(f"[green]✓ Successfully deleted schema '{schema_api_name}'.[/green]")
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)
from .field import field_app
schema_app.add_typer(field_app, name='field')

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/sync.py

```python
import typer
import json
from typing import Optional
from pathlib import Path
from rich.console import Console
from .auth import get_auth, get_api_base_url, get_project_root
from .scaffold import prepare_web_push
from .project import update_local_stubs

console = Console()
pull_app = typer.Typer(help="Download assets from the Valstorm cloud.")
push_app = typer.Typer(help="Upload local changes to the Valstorm cloud.")





@pull_app.command(name="metadata")
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

    # 2. Define the union of platform system types and custom object schemas
    SYSTEM_TYPES = {
        "record_trigger", "function", "automation", "ai_agent", "app", 
        "app_page", "app_metadata", "permission", "notification_setting", 
        "schedule_trigger_setting", "workspace"
    }
    schemas_set = set(available_schemas.keys() if isinstance(available_schemas, dict) else available_schemas)
    allowed_types = SYSTEM_TYPES.union(schemas_set)

    # 3. Define target types
    manifest_data = None
    manifest_file_path = None
    
    try:
        with open(root / "valstorm.json", "r") as f:
            config = json.load(f)
    except Exception:
        config = {}
        
    if manifest:
        manifest_file_path = Path(manifest)
    elif "manifest" in config:
        manifest_file_path = root / config["manifest"]
    elif (root / "manifest.json").exists():
        manifest_file_path = root / "manifest.json"
        
    if manifest_file_path:
        if not manifest_file_path.exists():
            console.print(f"[bold red]Manifest file not found:[/bold red] {manifest_file_path}")
            raise typer.Exit(1)
        with open(manifest_file_path, "r") as f:
            manifest_data = json.load(f).get("objects", {})
        target_types = [t for t in manifest_data.keys() if t in allowed_types]
    elif object_type:
        if object_type not in allowed_types:
            console.print(f"[bold red]Error:[/bold red] Object type '{object_type}' not found in schemas.")
            raise typer.Exit(1)
        target_types = [object_type]
    else:
        configured_objects = config.get("objects")
        
        if configured_objects:
            target_types = [t for t in configured_objects if t in allowed_types]
        else:
            core_types = ["record_trigger", "function", "automation"]
            metadata_types = [
                "ai_agent", "app", "app_page", "app_metadata", 
                "permission", "notification_setting", 
                "schedule_trigger_setting", "workspace"
            ]
            target_types = [t for t in (core_types + metadata_types) if t in allowed_types]
    
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
                rec_file_name = record.get("file_name")
                code = record.get("code")
                
                if rec_file_name and code:
                    file_path = target_dir / rec_file_name
                    
                    # Check if local file exists and has different content
                    if file_path.exists() and not force:
                        with open(file_path, "r") as f:
                            local_code = f.read()
                        if local_code != code:
                            choice = typer.prompt(
                                f"Local changes detected in {rec_file_name}. Overwrite? [y/N/a] (a=all)",
                                default="n"
                            ).lower()
                            
                            if choice == 'a':
                                force = True
                            elif choice != 'y':
                                console.print(f"Skipping {rec_file_name}")
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

@pull_app.command(name="schemas")
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

@push_app.command(name="metadata")
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
    manifest_file_path = None
    
    try:
        with open(root / "valstorm.json", "r") as f:
            config = json.load(f)
    except Exception:
        config = {}
        
    if manifest:
        manifest_file_path = Path(manifest)
    elif "manifest" in config:
        manifest_file_path = root / config["manifest"]
    elif (root / "manifest.json").exists():
        manifest_file_path = root / "manifest.json"
        
    if manifest_file_path:
        if not manifest_file_path.exists():
            console.print(f"[bold red]Manifest file not found:[/bold red] {manifest_file_path}")
            raise typer.Exit(1)
        with open(manifest_file_path, "r") as f:
            manifest_data = json.load(f).get("objects", {})
        types = [t for t in manifest_data.keys() if (object_root / t).exists()]
    elif api_name:
        types = [api_name]
    else:
        types = [d.name for d in object_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
        
        # Filter types by configuration if present
        configured_objects = config.get("objects")
        if configured_objects:
            types = [t for t in types if t in configured_objects]
    
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

@push_app.command(name="web")
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


```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/test_env.py

```python

import sys
import os
print("Executable:", sys.executable)
print("File:", __file__)

```

## /Users/jared/Documents/Code/valstorm/cli/src/valstorm_cli/vfs_cmds.py

```python
import json
import sys

import httpx
import typer
from rich.console import Console
from rich.table import Table

from .auth import get_api_base_url, get_auth

vfs_app = typer.Typer(help="Manage the Virtual File System (VFS)", no_args_is_help=True)
console = Console()

def handle_error(response: httpx.Response, json_output: bool):
    """Handles error reporting uniformly for VFS commands."""
    if response.status_code >= 400:
        # Check if response has been read (or is streaming)
        try:
            error_text = response.text
        except httpx.ResponseNotRead:
            response.read()
            error_text = response.text

        if json_output:
            print(json.dumps({"error": error_text, "status_code": response.status_code}))
        else:
            console.print(f"[bold red]API Error ({response.status_code}):[/bold red] {error_text}")
        
        if response.status_code in (401, 403):
            sys.exit(3)
        elif response.status_code == 404:
            sys.exit(4)
        else:
            sys.exit(2)

@vfs_app.command("list")
def vfs_list(
    vault_id: str | None = typer.Argument(None, help="Vault ID or Vault Name"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a formatted table"),
):
    """List files and directories in a given vault."""
    if not vault_id:
        vault_id = "root"
    auth = get_auth()
    base_url = get_api_base_url()
    
    with httpx.Client() as client:
        try:
            res = client.get(
                f"{base_url}/vfs/vault/{vault_id}",
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    # Rich output
    console.print(f"\n[bold]Contents of Vault:[/bold] {vault_id}\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="dim")
    table.add_column("Name")
    table.add_column("ID", style="cyan")

    for folder in data.get("folders", []):
        table.add_row("Directory", folder.get("name", "Unknown"), folder.get("id", ""))
        
    for f in data.get("files", []):
        table.add_row("File", f.get("name", "Unknown"), f.get("id", ""))

    console.print(table)


@vfs_app.command("query")
def vfs_query(
    query: str = typer.Option(..., "--query", help="SQL query string to search VFS metadata"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a formatted table"),
):
    """Query VFS metadata using a SQL-like syntax."""
    auth = get_auth()
    base_url = get_api_base_url()
    
    payload = {"query": query}

    with httpx.Client() as client:
        try:
            res = client.post(
                f"{base_url}/vfs/query",
                json=payload,
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    # Rich output
    if not data:
        console.print("[yellow]No results found.[/yellow]")
        return
        
    console.print("\n[bold]Query Results:[/bold]\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    if data and isinstance(data, list) and len(data) > 0:
        keys = list(data[0].keys())
        for k in keys[:5]: # Cap columns to prevent terminal explosion
            table.add_column(k)
            
        for row in data:
            row_data = [str(row.get(k, "")) for k in keys[:5]]
            table.add_row(*row_data)

    console.print(table)


@vfs_app.command("move")
def vfs_move(
    item_id: str = typer.Argument(..., help="The ID of the file or vault to move"),
    from_vault_id: str = typer.Option(..., help="The ID of the source vault"),
    to_vault_id: str = typer.Option(..., help="The ID of the destination vault"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a message"),
):
    """Move an item (vault or file) from one vault to another."""
    auth = get_auth()
    base_url = get_api_base_url()
    
    payload = {
        "item_id": item_id,
        "from_vault_id": from_vault_id,
        "to_vault_id": to_vault_id
    }

    with httpx.Client() as client:
        try:
            res = client.post(
                f"{base_url}/vfs/move",
                json=payload,
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    console.print(f"[green]Successfully moved item {item_id} to vault {to_vault_id}[/green]")

@vfs_app.command("rebuild-cache")
def vfs_rebuild_cache(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response"),
):
    """Rebuild the Virtual File System (VFS) cache from the source of truth."""
    auth = get_auth()
    base_url = get_api_base_url()

    if json_output:
        with httpx.Client() as client:
            try:
                res = client.post(
                    f"{base_url}/vfs/cache/rebuild",
                    headers={"Authorization": f"Bearer {auth.access_token}"}
                )
                handle_error(res, json_output)
                data = res.json()
            except httpx.RequestError as e:
                print(json.dumps({"error": str(e)}))
                sys.exit(2)
        print(json.dumps(data, indent=2))
        return

    with console.status("[bold cyan]Rebuilding VFS cache...[/bold cyan]"), httpx.Client() as client:
        try:
            res = client.post(
                f"{base_url}/vfs/cache/rebuild",
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    msg = data.get("message", "VFS cache rebuilt successfully.") if isinstance(data, dict) else "VFS cache rebuilt successfully."
    console.print(f"[green]{msg}[/green]")

@vfs_app.command("upload")
def vfs_upload(
    file_path: str = typer.Argument(..., help="Local path to the file to upload"),
    vault_id: str = typer.Argument(..., help="Destination Vault ID"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a message"),
):
    """Upload a file to VFS/S3"""
    import os
    auth = get_auth()
    base_url = get_api_base_url()
    
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        sys.exit(1)
        
    filename = os.path.basename(file_path)
    
    with httpx.Client(timeout=300.0) as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, "application/octet-stream")}
                data = {"vault_id": vault_id}
                
                res = client.post(
                    f"{base_url}/vfs/upload",
                    data=data,
                    files=files,
                    headers={"Authorization": f"Bearer {auth.access_token}"}
                )
                handle_error(res, json_output)
                response_data = res.json()
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    if json_output:
        print(json.dumps(response_data, indent=2))
        return

    console.print(f"[green]Successfully uploaded [bold]{filename}[/bold] to vault [bold]{vault_id}[/bold][/green]")
    if response_data.get("id"):
        console.print(f"File ID: [cyan]{response_data.get('id')}[/cyan]")


@vfs_app.command("download")
def vfs_download(
    file_id: str = typer.Argument(..., help="File ID to download"),
    destination_path: str | None = typer.Argument(None, help="Destination directory or file path"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON on error"),
):
    """Download a file from VFS/S3"""
    import os
    import re
    auth = get_auth()
    base_url = get_api_base_url()
    
    with httpx.Client(timeout=300.0) as client:
        try:
            with client.stream(
                "GET",
                f"{base_url}/vfs/download/{file_id}",
                headers={"Authorization": f"Bearer {auth.access_token}"}
            ) as res:
                handle_error(res, json_output)
                
                # Try to get filename from Content-Disposition
                filename = f"downloaded_{file_id}"
                cd = res.headers.get("content-disposition")
                if cd:
                    match = re.search(r'filename="?([^"]+)"?', cd)
                    if match:
                        filename = match.group(1)
                
                # Determine final output path
                out_path = filename
                if destination_path:
                    if os.path.isdir(destination_path):
                        out_path = os.path.join(destination_path, filename)
                    else:
                        out_path = destination_path
                
                # Stream to disk
                with open(out_path, "wb") as f:
                    for chunk in res.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        
                if not json_output:
                    console.print(f"[green]Successfully downloaded to [bold]{out_path}[/bold][/green]")
                    
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)


@vfs_app.command("delete")
def vfs_delete(
    item_id: str = typer.Argument(..., help="Vault or File ID to delete"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a message"),
):
    """Delete a file or vault from VFS/S3"""
    auth = get_auth()
    base_url = get_api_base_url()

    with httpx.Client() as client:
        try:
            res = client.delete(
                f"{base_url}/vfs/{item_id}",
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            
            # 204 No Content doesn't have json
            if res.status_code == 204:
                data = {"message": "success"}
            else:
                data = res.json()
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    console.print(f"[green]Successfully deleted [bold]{item_id}[/bold][/green]")

```

