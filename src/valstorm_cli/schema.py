import json
from pathlib import Path
from typing import List, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table
from valstorm import ValstormClient, ValstormError

from .auth import requires_auth

console = Console()
schema_app = typer.Typer(help="Manage Valstorm object schemas, fields, and PostgreSQL reflection.")


@schema_app.command("list")
@requires_auth
def list_schemas(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    List all schemas in the organization.
    """
    try:
        schemas = sdk.schemas.list()
    except ValstormError as e:
        console.print(f"[bold red]Failed to fetch schemas:[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(schemas, indent=2))
        return

    table = Table(title="Valstorm Schemas")
    table.add_column("API Name", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Prefix", style="magenta")
    table.add_column("Fields", justify="right")

    for s in schemas:
        if isinstance(s, dict):
            props = s.get("properties") or {}
            table.add_row(
                str(s.get("api_name", "")),
                str(s.get("title", "")),
                str(s.get("prefix", "")),
                str(len(props)) if isinstance(props, dict) else "-",
            )
    console.print(table)


@schema_app.command("get")
@requires_auth
def get_schema(
    api_name: str = typer.Argument(..., help="The API name of the schema (e.g., contact, ticket)."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Get the full JSON definition of a schema.
    """
    try:
        schema = sdk.schemas.get(api_name)
        print(json.dumps(schema, indent=2))
    except ValstormError as e:
        console.print(f"[bold red]Failed to fetch schema '{api_name}':[/bold red] {e}")
        raise typer.Exit(1)


@schema_app.command("create")
@requires_auth
def create_schema(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to a JSON schema file."),
    data: Optional[str] = typer.Option(None, "--data", "-d", help="Raw JSON string for the schema."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Create a new object schema.
    """
    payload = json.loads(Path(file).read_text()) if file else (json.loads(data) if data else None)
    if not payload:
        console.print("[bold red]Error:[/bold red] Must provide --file or --data.")
        raise typer.Exit(1)
    try:
        res_data = sdk.schemas.create(payload)
        print(json.dumps(res_data, indent=2))
    except ValstormError as e:
        console.print(f"[bold red]Failed to create schema:[/bold red] {e}")
        raise typer.Exit(1)


@schema_app.command("update")
@requires_auth
def update_schema(
    api_name: str = typer.Argument(..., help="The API name of the schema to update."),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to a JSON update payload."),
    data: Optional[str] = typer.Option(None, "--data", "-d", help="Raw JSON string for the update."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Update an existing object schema.
    """
    payload = json.loads(Path(file).read_text()) if file else (json.loads(data) if data else None)
    if not payload:
        console.print("[bold red]Error:[/bold red] Must provide --file or --data.")
        raise typer.Exit(1)
    try:
        res_data = sdk.schemas.update(api_name, payload)
        print(json.dumps(res_data, indent=2))
    except ValstormError as e:
        console.print(f"[bold red]Failed to update schema:[/bold red] {e}")
        raise typer.Exit(1)


@schema_app.command("delete")
@requires_auth
def delete_schema(
    api_name: str = typer.Argument(..., help="The API name of the schema to delete."),
    force: bool = typer.Option(False, "--force", "-y", help="Skip confirmation prompt."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Delete an object schema.
    """
    if not force:
        if not typer.confirm(f"Are you sure you want to delete schema '{api_name}'? This is destructive."):
            raise typer.Exit(0)
    try:
        sdk.schemas.delete(api_name)
        console.print(f"[green]✓ Successfully deleted schema '{api_name}'.[/green]")
    except ValstormError as e:
        console.print(f"[bold red]Failed to delete schema:[/bold red] {e}")
        raise typer.Exit(1)


@schema_app.command("status")
@requires_auth
def schema_sync_status(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Detect schema drift between physical PostgreSQL tables/columns and Valstorm metadata.
    """
    res = client.get("/schema/sync/status", timeout=30.0)
    if res.status_code != 200:
        console.print(f"[bold red]Failed to check schema drift ({res.status_code}):[/bold red] {res.text}")
        raise typer.Exit(1)

    data = res.json()
    if json_output:
        print(json.dumps(data, indent=2))
        return

    in_sync = data.get("is_in_sync") if "is_in_sync" in data else data.get("in_sync", False)
    if in_sync:
        console.print("[bold green]✓ PostgreSQL tables and Valstorm schemas are in sync.[/bold green]")
        return

    console.print("[bold yellow]Schema drift detected between PostgreSQL and Valstorm metadata:[/bold yellow]")
    untracked = data.get("unregistered_tables") or data.get("untracked_tables") or []
    if untracked:
        console.print(f"  [cyan]Unregistered PostgreSQL tables ({len(untracked)}):[/cyan] {', '.join(untracked)}")

    missing_tables = data.get("missing_tables") or []
    if missing_tables:
        console.print(f"  [red]Missing physical tables ({len(missing_tables)}):[/red] {', '.join(missing_tables)}")

    column_drift = data.get("table_drift") or data.get("column_drift") or {}
    if column_drift:
        table = Table(title="Column Drift")
        table.add_column("Table", style="cyan")
        table.add_column("Unregistered PG Columns", style="green")
        table.add_column("Deleted PG Columns", style="red")
        for tbl, diff in column_drift.items():
            added = ", ".join(diff.get("unregistered_columns") or diff.get("added") or diff.get("untracked_columns") or [])
            removed = ", ".join(diff.get("deleted_columns") or diff.get("removed") or diff.get("missing_columns") or [])
            table.add_row(tbl, added or "-", removed or "-")
        console.print(table)

    console.print("\nRun [bold]valstorm schema sync[/bold] to introspect PostgreSQL changes into Valstorm.")


@schema_app.command("sync")
@requires_auth
def sync_schemas_from_postgres(
    objects: Optional[List[str]] = typer.Option(
        None,
        "--object",
        "-o",
        help="Specific PostgreSQL table name(s) to sync (repeatable; defaults to all tables).",
    ),
    prune: bool = typer.Option(
        False,
        "--prune",
        help="Remove Valstorm schema fields whose underlying PostgreSQL columns were dropped.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Introspect native PostgreSQL tables/columns (e.g. after Alembic/Prisma/SQL migrations)
    and synchronize them into Valstorm schemas metadata.
    """
    payload = {
        "objects": list(objects) if objects else None,
        "prune_missing_columns": prune,
    }
    res = client.post("/schema/sync", json=payload, timeout=60.0)
    if res.status_code not in (200, 201):
        console.print(f"[bold red]Schema sync failed ({res.status_code}):[/bold red] {res.text}")
        raise typer.Exit(1)

    data = res.json()
    if json_output:
        print(json.dumps(data, indent=2))
        return

    console.print("[bold green]✓ PostgreSQL schema sync complete![/bold green]")
    created = data.get("created_schemas") or data.get("created") or []
    updated = data.get("updated_schemas") or data.get("updated") or []
    if created:
        console.print(f"  Created schemas: [green]{', '.join(map(str, created))}[/green]")
    if updated:
        console.print(f"  Updated schemas: [cyan]{', '.join(map(str, updated))}[/cyan]")
    if not created and not updated:
        console.print("  [dim]No schema changes were required.[/dim]")


from .field import field_app  # noqa: E402

schema_app.add_typer(field_app, name="field")
