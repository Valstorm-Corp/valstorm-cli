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
