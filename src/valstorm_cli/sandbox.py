import typer
import httpx
from typing import Optional, List
from rich.console import Console
from .auth import ValstormAuth, requires_auth, get_project_root, load_config

console = Console()
sandbox_app = typer.Typer(help="Manage developer sandboxes.")

users_app = typer.Typer(help="Manage users in a sandbox.")
sandbox_app.add_typer(users_app, name="users")

@sandbox_app.command("create")
@requires_auth(use_parent=True)
def create_sandbox(
    name: str = typer.Argument(..., help="Lowercase alphanumeric name for the sandbox (e.g., 'dev')."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Markdown description for the sandbox."),
    client: httpx.Client = None,  # type: ignore
):
    """Provisions a new sandbox database and copies configuration."""
    payload = {"name": name}
    if description:
        payload["description"] = description
        
    console.print(f"Creating sandbox [bold cyan]{name}[/bold cyan]...")
    try:
        response = client.post("/sandbox", json=payload, timeout=120.0)
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
@requires_auth(use_parent=True)
def list_sandboxes(
    client: httpx.Client = None,  # type: ignore
):
    """Lists all sandbox environments associated with the active production organization."""
    console.print("Fetching sandboxes...")
    try:
        response = client.get("/sandbox", timeout=30.0)
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
@requires_auth(use_parent=True)
def refresh_sandbox(
    name: str = typer.Argument(..., help="Sandbox name to refresh (e.g., 'dev')"),
    client: httpx.Client = None,  # type: ignore
):
    """Wipes the sandbox database and re-clones configuration from production."""
    console.print(f"Refreshing sandbox [bold cyan]{name}[/bold cyan]... (This may take a minute)")
    try:
        response = client.post(f"/sandbox/{name}/refresh", timeout=180.0)
        response.raise_for_status()
        console.print(f"[bold green]✓ Sandbox '{name}' refreshed successfully![/bold green]")
    except httpx.HTTPStatusError as e:
        console.print(f"[bold red]Error ({e.response.status_code}):[/bold red] {e.response.text}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to refresh sandbox:[/bold red] {str(e)}")
        raise typer.Exit(1)

@sandbox_app.command("delete")
@requires_auth(use_parent=True)
def delete_sandbox(
    name: str = typer.Argument(..., help="Sandbox name to delete (e.g., 'dev')"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without prompting."),
    client: httpx.Client = None,  # type: ignore
):
    """Permanently deletes a sandbox and all its contents."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to permanently delete the sandbox '{name}'?")
        if not confirm:
            console.print("Operation cancelled.")
            raise typer.Exit()
            
    console.print(f"Deleting sandbox [bold cyan]{name}[/bold cyan]...")
    try:
        response = client.delete(f"/sandbox/{name}", timeout=120.0)
        response.raise_for_status()
        console.print(f"[bold green]✓ Sandbox '{name}' deleted successfully![/bold green]")
    except httpx.HTTPStatusError as e:
        console.print(f"[bold red]Error ({e.response.status_code}):[/bold red] {e.response.text}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Failed to delete sandbox:[/bold red] {str(e)}")
        raise typer.Exit(1)

@users_app.command("add")
@requires_auth(use_parent=True)
def add_users(
    name: str = typer.Argument(..., help="Sandbox name"),
    users: List[str] = typer.Argument(..., help="List of User IDs or Emails to add"),
    client: httpx.Client = None,  # type: ignore
):
    """Add users to a sandbox environment."""
    console.print(f"Adding users to sandbox [bold cyan]{name}[/bold cyan]...")
    try:
        response = client.post(f"/sandbox/{name}/users", json={"users": users}, timeout=60.0)
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
@requires_auth(use_parent=True)
def remove_users(
    name: str = typer.Argument(..., help="Sandbox name"),
    users: List[str] = typer.Argument(..., help="List of User IDs or Emails to remove"),
    client: httpx.Client = None,  # type: ignore
):
    """Remove users from a sandbox environment."""
    console.print(f"Removing users from sandbox [bold cyan]{name}[/bold cyan]...")
    try:
        response = client.request(
            method="DELETE",
            url=f"/sandbox/{name}/users",
            json={"users": users},
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
@requires_auth(use_parent=True)
def use_sandbox(
    name: str = typer.Argument(..., help="The name of the sandbox to switch to."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Switch the local workspace target to a specific sandbox.
    """
    import json
    
    try:
        root = get_project_root()
    except Exception:
        console.print("[bold red]Not in a Valstorm project directory.[/bold red]")
        raise typer.Exit(1)
        
    config = load_config(root)
    
    # Optional: Verify sandbox actually exists in parent org by listing them
    try:
        res = client.get("/sandbox", timeout=10.0)
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
