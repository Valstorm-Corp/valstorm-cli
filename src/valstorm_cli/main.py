import typer
import httpx
from rich.console import Console
import getpass
import os
import json
import shutil
from pathlib import Path
from .auth import ValstormAuth, get_api_base_url

app = typer.Typer(help="Valstorm Developer CLI", no_args_is_help=True)
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
            console.print("[bold green]Successfully logged in![/bold green]")
        else:
            console.print("[bold red]Unexpected response during login.[/bold red]")
            console.print(data)

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
    
    # 2. Create Directory Structure
    object_dir = target_path / "object"
    (object_dir / "record_trigger").mkdir(parents=True, exist_ok=True)
    (object_dir / "function").mkdir(parents=True, exist_ok=True)
    
    platform_dir = target_path / "valstorm_platform"
    platform_dir.mkdir(exist_ok=True)
    
    # Create __init__.py to make it a module
    with open(platform_dir / "__init__.py", "w") as f:
        f.write("# Valstorm Platform SDK\n")
    
    # 3. Copy Stubs for IDE support
    current_dir = Path(__file__).parent
    source_stubs = current_dir / "stubs" / "platform_context.py"
    
    if source_stubs.exists():
        shutil.copy(source_stubs, platform_dir / "platform_context.py")
        console.print("[green]✓[/green] PlatformContext copied for intellisense.")
    else:
        console.print("[yellow]![/yellow] Warning: Could not find built-in stubs to copy.")

    # 4. Create a README
    with open(target_path / "README.md", "w") as f:
        f.write(f"# Valstorm Project: {target_path.name}\n\nLocal development environment for Valstorm triggers and functions.\n")

    # 5. Create a .gitignore
    with open(target_path / ".gitignore", "w") as f:
        f.write("__pycache__/\n*.pyc\n.env\n")

    console.print(f"\n[bold green]🚀 Project initialized successfully in {target_path.absolute()}[/bold green]")
    console.print(f"Next steps:\n  1. [cyan]cd {target_path.name}[/cyan]\n  2. [cyan]valstorm pull[/cyan]\n  3. Start coding in [blue]object/record_trigger/[/blue] or [blue]object/function/[/blue]")

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
    """Copies the latest platform_context.py from the CLI package to the project."""
    platform_dir = target_path / "valstorm_platform"
    platform_dir.mkdir(exist_ok=True)
    
    # Ensure __init__.py exists
    init_file = platform_dir / "__init__.py"
    if not init_file.exists():
        with open(init_file, "w") as f:
            f.write("# Valstorm Platform SDK\n")
            
    current_dir = Path(__file__).parent
    source_stubs = current_dir / "stubs" / "platform_context.py"
    dest_stubs = platform_dir / "platform_context.py"
    
    if source_stubs.exists():
        # Check if an update is actually needed by comparing file contents or modification times
        # For simplicity, we just overwrite if they differ
        needs_update = True
        if dest_stubs.exists():
            with open(source_stubs, "r") as src, open(dest_stubs, "r") as dst:
                if src.read() == dst.read():
                    needs_update = False
                    
        if needs_update:
            shutil.copy(source_stubs, dest_stubs)
            if not silent:
                console.print("[green]✓[/green] PlatformContext stubs updated for intellisense.")
        elif not silent:
            console.print("[dim]PlatformContext stubs are already up-to-date.[/dim]")
    elif not silent:
        console.print("[yellow]![/yellow] Warning: Could not find built-in stubs to copy.")

@app.command(name="update-stubs")
def update_stubs_command():
    """
    Update the local PlatformContext stubs to the version bundled with the CLI.
    """
    root = get_project_root()
    update_local_stubs(root)

@app.command()
def pull(
    force: bool = typer.Option(False, "--force", help="Overwrite local changes without asking."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Download record triggers and functions from the Valstorm cloud.
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

    types = ["record_trigger", "function"]
    
    for file_type in types:
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

            # Extract code
            count = 0
            for record in records:
                file_name = record.get("file_name")
                code = record.get("code")
                
                if file_name and code:
                    file_path = target_dir / file_name
                    
                    # Check if local file exists and has different content
                    if file_path.exists() and not force:
                        with open(file_path, "r") as f:
                            local_code = f.read()
                        if local_code != code:
                            if not typer.confirm(f"Local changes detected in {file_name}. Overwrite?"):
                                console.print(f"Skipping {file_name}")
                                continue
                    
                    with open(file_path, "w") as f:
                        f.write(code)
                    count += 1
            
            console.print(f"[green]✓[/green] Synchronized {count} {file_type} files.")

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

    types = ["record_trigger", "function"]
    
    for file_type in types:
        local_dir = root / "object" / file_type
        metadata_path = local_dir / f"{file_type}_metadata.json"
        
        metadata = []
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
        updates_payload = []
        creates_payload = []
        
        if not local_dir.exists():
            continue

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

@app.callback()
def main():
    """
    Valstorm Developer CLI.
    """
    pass

if __name__ == "__main__":
    app()
