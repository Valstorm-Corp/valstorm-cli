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

