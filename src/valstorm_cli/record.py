import typer
import httpx
import json
from typing import Optional, List
from rich.console import Console
from .auth import ValstormAuth, requires_auth

console = Console()
record_app = typer.Typer(help="Manage records", no_args_is_help=True)

LOOKUP_SUMMARY_KEYS = {"id", "name", "label", "schema", "schema_api_name", "schema_title", "_id"}

def unpack_hydrated_lookups(data):
    """
    Recursively unpacks hydrated lookup dictionaries {'id': '...'} into raw ID strings.
    Leaves non-lookup dictionaries intact.
    """
    if isinstance(data, dict):
        if "id" in data and isinstance(data["id"], str) and set(data.keys()).issubset(LOOKUP_SUMMARY_KEYS):
            return data["id"]
        return {k: unpack_hydrated_lookups(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [unpack_hydrated_lookups(item) for item in data]
    return data

def load_data(data: Optional[str], file: Optional[str]) -> List[dict]:
    if file:
        try:
            with open(file, 'r') as f:
                content = json.load(f)
                loaded = content if isinstance(content, list) else [content]
                return unpack_hydrated_lookups(loaded)
        except Exception as e:
            console.print(f"[bold red]Failed to read file:[/bold red] {e}")
            raise typer.Exit(1)
    elif data:
        try:
            content = json.loads(data)
            loaded = content if isinstance(content, list) else [content]
            return unpack_hydrated_lookups(loaded)
        except Exception as e:
            console.print(f"[bold red]Failed to parse data JSON:[/bold red] {e}")
            raise typer.Exit(1)
    else:
        console.print("[bold red]Must provide either --data or --file.[/bold red]")
        raise typer.Exit(1)

@record_app.command(name="create")
@requires_auth
def create_record(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema/object."),
    data: Optional[str] = typer.Option(None, "--data", help="JSON string of record data."),
    file: Optional[str] = typer.Option(None, "--file", help="JSON file containing record data."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None  # type: ignore
):
    """Create one or multiple records."""
    payload = load_data(data, file)
    res = client.post(f"/object/{schema_api_name}", json=payload)
    if res.status_code not in (200, 201):
        console.print(f"[bold red]Failed to create record(s):[/bold red] {res.text}")
        raise typer.Exit(1)
    console.print("[green]✓ Successfully created record(s).[/green]")
    console.print_json(data=res.json())

@record_app.command(name="update")
@requires_auth
def update_record(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema/object."),
    data: Optional[str] = typer.Option(None, "--data", help="JSON string of update data (must include 'id')."),
    file: Optional[str] = typer.Option(None, "--file", help="JSON file containing update data."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None  # type: ignore
):
    """Update existing records."""
    payload = load_data(data, file)
    res = client.patch(f"/object/{schema_api_name}", json=payload)
    if res.status_code != 200:
        console.print(f"[bold red]Failed to update record(s):[/bold red] {res.text}")
        raise typer.Exit(1)
    console.print("[green]✓ Successfully updated record(s).[/green]")
    console.print_json(data=res.json())

@record_app.command(name="delete")
@requires_auth
def delete_record(
    schema_api_name: str = typer.Argument(..., help="The API name of the schema/object."),
    id: Optional[List[str]] = typer.Option(None, "--id", help="Record ID to delete (can be specified multiple times)."),
    file: Optional[str] = typer.Option(None, "--file", help="JSON file containing array of IDs."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None  # type: ignore
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

    res = client.request("DELETE", f"/object/{schema_api_name}", params={"ids": ids_to_delete})
    if res.status_code != 200:
        console.print(f"[bold red]Failed to delete record(s):[/bold red] {res.text}")
        raise typer.Exit(1)
    console.print(f"[green]✓ Successfully deleted {len(ids_to_delete)} record(s).[/green]")
