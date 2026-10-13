import typer
import httpx
import json
from typing import Optional
from rich.console import Console
from valstorm import ValstormClient, ValstormError
from .auth import ValstormAuth, requires_auth

console = Console()
schema_app = typer.Typer(help="Manage schemas / objects", no_args_is_help=True)

@schema_app.command(name="list")
@requires_auth
def list_schemas(
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None  # type: ignore
):
    """List all schemas."""
    try:
        data = sdk.schemas.list()
        console.print_json(data=data)
    except ValstormError as e:
        console.print(f"[bold red]Failed to list schemas:[/bold red] {e}")
        raise typer.Exit(1)

@schema_app.command(name="get")
@requires_auth
def get_schema(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema."),
    output: str = typer.Option("json", "--output", "-o", help="Output format."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None  # type: ignore
):
    """Get a specific schema definition."""
    try:
        data = sdk.schemas.get(schema_api_name)
        console.print_json(data=data)
    except ValstormError as e:
        console.print(f"[bold red]Failed to get schema:[/bold red] {e}")
        raise typer.Exit(1)

@schema_app.command(name="create")
@requires_auth
def create_schema(
    name: Optional[str] = typer.Argument(None, help="The display name of the schema."),
    api_name: Optional[str] = typer.Option(None, "--api-name", help="The API name of the schema."),
    file: Optional[str] = typer.Option(None, "--file", help="JSON file containing the schema definition."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None  # type: ignore
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

    try:
        res = sdk.schemas.create(payload)
        console.print("[green]✓ Successfully created schema.[/green]")
        console.print_json(data=res)
    except ValstormError as e:
        console.print(f"[bold red]Failed to create schema:[/bold red] {e}")
        raise typer.Exit(1)

@schema_app.command(name="update")
@requires_auth
def update_schema(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema."),
    data: str = typer.Option(..., "--data", help="JSON string of schema metadata to update."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None  # type: ignore
):
    """Update an existing schema metadata."""
    try:
        payload = json.loads(data)
    except Exception as e:
        console.print(f"[bold red]Failed to parse JSON data:[/bold red] {e}")
        raise typer.Exit(1)

    try:
        if isinstance(payload, dict) and "api_name" not in payload:
            payload["api_name"] = schema_api_name
        res = sdk.schemas.update(payload)
        console.print("[green]✓ Successfully updated schema.[/green]")
        console.print_json(data=res)
    except ValstormError as e:
        console.print(f"[bold red]Failed to update schema:[/bold red] {e}")
        raise typer.Exit(1)

@schema_app.command(name="delete")
@requires_auth
def delete_schema(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema."),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None  # type: ignore
):
    """Delete a schema."""
    if not confirm:
        if not typer.confirm(f"Are you sure you want to delete schema '{schema_api_name}'?"):
            raise typer.Exit()

    try:
        sdk.schemas.delete(schema_api_name)
        console.print(f"[green]✓ Successfully deleted schema '{schema_api_name}'.[/green]")
    except ValstormError as e:
        console.print(f"[bold red]Failed to delete schema:[/bold red] {e}")
        raise typer.Exit(1)

from .field import field_app
schema_app.add_typer(field_app, name='field')
