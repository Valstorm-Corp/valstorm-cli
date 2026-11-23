import json
from pathlib import Path
from typing import List, Optional

import httpx
import typer
from rich.console import Console
from valstorm import ValstormClient, ValstormError

from .auth import requires_auth

console = Console()
record_app = typer.Typer(help="Manage Valstorm records (get, create, update, delete, restore).")


def unpack_hydrated_lookups(obj):
    """
    Recursively converts hydrated lookup objects ({'id': '...', 'name': '...'})
    back into plain string IDs, preserving data integrity on writes.
    """
    if isinstance(obj, list):
        return [unpack_hydrated_lookups(item) for item in obj]
    if isinstance(obj, dict):
        keys = set(obj.keys())
        if "id" in keys and keys.issubset({"id", "name", "api_name", "schema_api_name"}):
            return obj["id"]
        return {k: unpack_hydrated_lookups(v) for k, v in obj.items()}
    return obj


def load_data(data: Optional[str], file: Optional[str]):
    if file:
        p = Path(file)
        if not p.exists():
            console.print(f"[bold red]Error:[/bold red] File '{file}' not found.")
            raise typer.Exit(1)
        try:
            parsed = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Invalid JSON in file '{file}':[/bold red] {e}")
            raise typer.Exit(1)
    elif data:
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Invalid JSON in --data:[/bold red] {e}")
            raise typer.Exit(1)
    else:
        console.print("[bold red]Error:[/bold red] Must provide either --data or --file.")
        raise typer.Exit(1)

    if isinstance(parsed, dict):
        parsed = [parsed]
    elif not isinstance(parsed, list):
        console.print("[bold red]Error:[/bold red] Payload must be a JSON object or an array of JSON objects.")
        raise typer.Exit(1)

    return [unpack_hydrated_lookups(item) for item in parsed]


@record_app.command("get")
@requires_auth
def get_record(
    object_api_name: str = typer.Argument(..., help="The API name of the object (e.g., contact, ticket)."),
    record_id: str = typer.Argument(..., help="The record ID to fetch."),
    hydrate: bool = typer.Option(
        False,
        "--hydrate",
        help="Hydrate lookup fields into {id, name} objects (default: off, returning raw string IDs).",
    ),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Fetch a single record by ID. Returns raw lookup IDs by default unless `--hydrate` is passed.
    """
    res = client.get(f"/object/{object_api_name}/{record_id}", params={"hydrate": str(hydrate).lower()})
    if res.status_code != 200:
        console.print(f"[bold red]Failed to fetch record ({res.status_code}):[/bold red] {res.text}")
        raise typer.Exit(1)
    print(json.dumps(res.json(), indent=2))


@record_app.command("create")
@requires_auth
def create_record(
    object_api_name: str = typer.Argument(..., help="The API name of the object (e.g., contact, ticket)."),
    data: Optional[str] = typer.Option(None, "--data", "-d", help="JSON string of the record (or array of records) to create."),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to a JSON file containing record(s) to create."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Create one or more records in Valstorm.
    """
    payload = load_data(data, file)
    try:
        res_data = sdk.records.create(object_api_name, payload)
        print(json.dumps(res_data, indent=2))
    except ValstormError as e:
        console.print(f"[bold red]Failed to create record(s):[/bold red] {e}")
        raise typer.Exit(1)


@record_app.command("update")
@requires_auth
def update_record(
    object_api_name: str = typer.Argument(..., help="The API name of the object (e.g., contact, ticket)."),
    record_id: Optional[str] = typer.Option(None, "--id", help="The ID of the record to update (if not present in JSON data)."),
    data: Optional[str] = typer.Option(None, "--data", "-d", help="JSON string of the record(s) to update."),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to a JSON file containing record(s) to update."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Update one or more records in Valstorm.
    """
    payload = load_data(data, file)
    if record_id:
        for item in payload:
            if isinstance(item, dict) and "id" not in item:
                item["id"] = record_id

    for item in payload:
        if isinstance(item, dict) and "id" not in item:
            console.print("[bold red]Error:[/bold red] All records in an update payload must include an 'id' field (or pass --id).")
            raise typer.Exit(1)

    try:
        res_data = sdk.records.update(object_api_name, payload)
        print(json.dumps(res_data, indent=2))
    except ValstormError as e:
        console.print(f"[bold red]Failed to update record(s):[/bold red] {e}")
        raise typer.Exit(1)


@record_app.command("delete")
@requires_auth
def delete_record(
    object_api_name: str = typer.Argument(..., help="The API name of the object (e.g., contact, ticket)."),
    ids: List[str] = typer.Argument(..., help="One or more record IDs to soft-delete."),
    force: bool = typer.Option(False, "--force", "-y", help="Skip confirmation prompt."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Soft-delete one or more records by ID.
    """
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete {len(ids)} record(s) from '{object_api_name}'?")
        if not confirm:
            console.print("Operation cancelled.")
            raise typer.Exit(0)

    try:
        sdk.records.delete(object_api_name, ids)
        console.print(f"[green]✓ Successfully deleted {len(ids)} record(s).[/green]")
    except ValstormError as e:
        console.print(f"[bold red]Failed to delete record(s):[/bold red] {e}")
        raise typer.Exit(1)


@record_app.command("restore")
@requires_auth
def restore_record(
    object_api_name: str = typer.Argument(..., help="The API name of the object (e.g., contact, ticket)."),
    ids: List[str] = typer.Argument(..., help="One or more soft-deleted record IDs to restore."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Restore one or more soft-deleted records from the recycle bin.
    """
    res = client.post(f"/object/{object_api_name}/undelete", json={"ids": ids})
    if res.status_code not in (200, 201):
        console.print(f"[bold red]Failed to restore record(s) ({res.status_code}):[/bold red] {res.text}")
        raise typer.Exit(1)
    console.print(f"[green]✓ Restored {len(ids)} record(s) in '{object_api_name}'.[/green]")
