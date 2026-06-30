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

