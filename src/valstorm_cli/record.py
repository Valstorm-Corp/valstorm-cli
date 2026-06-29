import typer
import httpx
import json
from typing import Optional, List
from pathlib import Path
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
            res = client.request("DELETE", f"/object/{schema_api_name}", json={"ids": ids_to_delete})
            if res.status_code != 200:
                console.print(f"[bold red]Failed to delete record(s):[/bold red] {res.text}")
                raise typer.Exit(1)
            console.print(f"[green]✓ Successfully deleted {len(ids_to_delete)} record(s).[/green]")
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)
