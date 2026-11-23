import json
from typing import List, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

from .auth import find_project_root, requires_auth

console = Console()
sandbox_app = typer.Typer(help="Manage Valstorm isolated PostgreSQL sandboxes.")
users_app = typer.Typer(help="Manage users with access to a sandbox.")
sandbox_app.add_typer(users_app, name="users")


@sandbox_app.command("create")
@requires_auth(use_parent=True)
def create_sandbox(
    name: str = typer.Argument(..., help="The name of the new sandbox."),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Optional description."),
    copy_data: bool = typer.Option(False, "--copy-data", help="Copy data from production instead of schema-only."),
    users: Optional[List[str]] = typer.Option(None, "--user", "-u", help="User email(s) to grant sandbox access."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Create a new sandbox organization.
    """
    payload = {"name": name, "description": description, "copy_data": copy_data}
    if users:
        payload["users"] = users

    console.print(f"Creating sandbox '[bold cyan]{name}[/bold cyan]'...")
    response = client.post("/sandbox/create", json=payload, timeout=120.0)
    if response.status_code in (200, 201):
        data = response.json()
        console.print(f"[bold green]✓ Successfully created sandbox '{name}'![/bold green]")
        if "sandbox_org_id" in data:
            console.print(f"Sandbox Org ID: [cyan]{data['sandbox_org_id']}[/cyan]")
    else:
        console.print(f"[bold red]Failed to create sandbox ({response.status_code}):[/bold red] {response.text}")
        raise typer.Exit(1)


@sandbox_app.command("list")
@requires_auth(use_parent=True)
def list_sandboxes(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    List all sandboxes for your organization.
    """
    response = client.get("/sandbox/list", timeout=30.0)
    if response.status_code != 200:
        console.print(f"[bold red]Failed to list sandboxes ({response.status_code}):[/bold red] {response.text}")
        raise typer.Exit(1)

    sandboxes = response.json()
    if json_output:
        print(json.dumps(sandboxes, indent=2))
        return

    if not sandboxes:
        console.print("[yellow]No sandboxes found.[/yellow]")
        return

    table = Table(title="Organization Sandboxes")
    table.add_column("Name", style="cyan")
    table.add_column("Sandbox Org ID", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Created Date", style="dim")

    for sb in sandboxes:
        if isinstance(sb, dict):
            table.add_row(
                str(sb.get("name", "")),
                str(sb.get("id", sb.get("sandbox_org_id", ""))),
                str(sb.get("status", "Active")),
                str(sb.get("created_date", "")),
            )
    console.print(table)


@sandbox_app.command("refresh")
@requires_auth(use_parent=True)
def refresh_sandbox(
    name: str = typer.Argument(..., help="The name of the sandbox to refresh."),
    copy_data: bool = typer.Option(False, "--copy-data", help="Copy data from production during refresh."),
    force: bool = typer.Option(False, "--force", "-y", help="Skip confirmation prompt."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Refresh a sandbox with the latest schemas/config (and optional data) from production.
    """
    if not force:
        if not typer.confirm(f"Are you sure you want to refresh sandbox '{name}'? All uncommitted changes will be overwritten."):
            console.print("Operation cancelled.")
            raise typer.Exit(0)

    console.print(f"Refreshing sandbox '[bold cyan]{name}[/bold cyan]'...")
    response = client.post(f"/sandbox/{name}/refresh", json={"copy_data": copy_data}, timeout=120.0)
    if response.status_code in (200, 201):
        console.print(f"[bold green]✓ Successfully refreshed sandbox '{name}'![/bold green]")
    else:
        console.print(f"[bold red]Failed to refresh sandbox ({response.status_code}):[/bold red] {response.text}")
        raise typer.Exit(1)


@sandbox_app.command("delete")
@requires_auth(use_parent=True)
def delete_sandbox(
    name: str = typer.Argument(..., help="The name of the sandbox to delete."),
    force: bool = typer.Option(False, "--force", "-y", help="Skip confirmation prompt."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Delete a sandbox organization permanently.
    """
    if not force:
        if not typer.confirm(f"Are you sure you want to PERMANENTLY delete sandbox '{name}'?"):
            console.print("Operation cancelled.")
            raise typer.Exit(0)

    console.print(f"Deleting sandbox '[bold red]{name}[/bold red]'...")
    response = client.delete(f"/sandbox/{name}", timeout=60.0)
    if response.status_code in (200, 204):
        console.print(f"[bold green]✓ Successfully deleted sandbox '{name}'.[/bold green]")
    else:
        console.print(f"[bold red]Failed to delete sandbox ({response.status_code}):[/bold red] {response.text}")
        raise typer.Exit(1)


@users_app.command("add")
@requires_auth(use_parent=True)
def add_users(
    name: str = typer.Argument(..., help="The name of the sandbox."),
    users: List[str] = typer.Argument(..., help="User emails or IDs to add to the sandbox."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Grant users access to a sandbox.
    """
    response = client.post(f"/sandbox/{name}/users", json={"users": users}, timeout=60.0)
    if response.status_code in (200, 201):
        console.print(f"[bold green]✓ Added {len(users)} user(s) to sandbox '{name}'.[/bold green]")
    else:
        console.print(f"[bold red]Failed to add users ({response.status_code}):[/bold red] {response.text}")
        raise typer.Exit(1)


@users_app.command("remove")
@requires_auth(use_parent=True)
def remove_users(
    name: str = typer.Argument(..., help="The name of the sandbox."),
    users: List[str] = typer.Argument(..., help="User emails or IDs to remove from the sandbox."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Revoke users' access to a sandbox.
    """
    response = client.request("DELETE", f"/sandbox/{name}/users", json={"users": users}, timeout=60.0)
    if response.status_code in (200, 204):
        console.print(f"[bold green]✓ Removed {len(users)} user(s) from sandbox '{name}'.[/bold green]")
    else:
        console.print(f"[bold red]Failed to remove users ({response.status_code}):[/bold red] {response.text}")
        raise typer.Exit(1)


@sandbox_app.command("use")
def use_sandbox(
    name: Optional[str] = typer.Argument(None, help="The sandbox name to target (omit when using --parent)."),
    parent: bool = typer.Option(False, "--parent", help="Switch back to the parent/production organization."),
):
    """
    Configure the current project (`valstorm.json`) to target a sandbox, or pass `--parent` to return to production.
    """
    root = find_project_root()
    if not root:
        console.print("[bold red]Error:[/bold red] Not in a Valstorm project directory (missing valstorm.json).")
        raise typer.Exit(1)

    config_path = root / "valstorm.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        console.print(f"[bold red]Error reading valstorm.json:[/bold red] {e}")
        raise typer.Exit(1)

    if parent or (name and name.lower() in ("parent", "prod", "none")):
        if "sandbox" in config:
            old_sb = config.pop("sandbox")
            config_path.write_text(json.dumps(config, indent=4), encoding="utf-8")
            console.print(f"[bold green]✓ Switched back to parent organization[/bold green] (exited sandbox '{old_sb}').")
        else:
            console.print("[yellow]Project is already targeting the parent organization.[/yellow]")
        return

    if not name:
        console.print("[bold red]Error:[/bold red] Provide a sandbox name or pass `--parent`.")
        raise typer.Exit(1)

    config["sandbox"] = name
    config_path.write_text(json.dumps(config, indent=4), encoding="utf-8")
    console.print(f"[bold green]✓ Active workspace sandbox set to '[bold cyan]{name}[/bold cyan]'.[/bold green]")
    console.print("Run [bold]valstorm sandbox use --parent[/bold] to switch back to production.")
