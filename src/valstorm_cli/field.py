import typer
import httpx
import json
from typing import Optional
from pathlib import Path
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
