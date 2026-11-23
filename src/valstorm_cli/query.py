import csv
import json
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from valstorm import ValstormClient, ValstormError

from .auth import requires_auth

console = Console()
query_app = typer.Typer(help="Execute SQL or GraphQL queries against Valstorm.")

_HYDRATED_LOOKUP_KEYS = frozenset({"id", "name", "api_name", "schema_api_name"})


def _is_hydrated_lookup_dict(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "id" in value
        and isinstance(value["id"], str)
        and set(value.keys()).issubset(_HYDRATED_LOOKUP_KEYS)
    )


def strip_hydrated_record_fields(record: Any) -> Any:
    """Unpacks hydrated lookup dicts ({id, name}) on a single record to raw string IDs."""
    if not isinstance(record, dict):
        return record
    cleaned: dict[str, Any] = {}
    for key, value in record.items():
        if _is_hydrated_lookup_dict(value):
            cleaned[key] = value["id"]
        elif isinstance(value, list) and value and all(_is_hydrated_lookup_dict(item) for item in value):
            cleaned[key] = [item["id"] for item in value]
        else:
            cleaned[key] = value
    return cleaned


def strip_hydrated_graphql_response(response_data: Any) -> Any:
    """
    Unpacks nested {id, name} lookup objects inside GraphQL record fields to raw IDs
    while leaving top-level records and richer relational joins intact.
    """
    if not isinstance(response_data, dict):
        return response_data
    data_section = response_data.get("data")
    if not isinstance(data_section, dict):
        return response_data

    cleaned_data: dict[str, Any] = {}
    for field_name, field_val in data_section.items():
        if isinstance(field_val, list):
            cleaned_data[field_name] = [strip_hydrated_record_fields(item) for item in field_val]
        elif isinstance(field_val, dict):
            cleaned_data[field_name] = strip_hydrated_record_fields(field_val)
        else:
            cleaned_data[field_name] = field_val

    return {**response_data, "data": cleaned_data}


def handle_query_save_and_output(data: Any, output: Optional[str], save: Optional[str], csv_file: Optional[str]):
    if output:
        Path(output).write_text(json.dumps(data, indent=2))
        console.print(f"[green]✓ Saved results to {output}[/green]")
    elif csv_file:
        records = data
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], dict):
                first_key = next(iter(data["data"]), None)
                if first_key and isinstance(data["data"][first_key], list):
                    records = data["data"][first_key]
            elif "records" in data and isinstance(data["records"], list):
                records = data["records"]

        if not isinstance(records, list) or not records:
            console.print("[yellow]No tabular records found to export to CSV.[/yellow]")
            return

        keys: list[str] = []
        for rec in records:
            if isinstance(rec, dict):
                for k in rec.keys():
                    if k not in keys:
                        keys.append(k)

        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for rec in records:
                if isinstance(rec, dict):
                    row = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in rec.items()}
                    writer.writerow(row)
        console.print(f"[green]✓ Exported {len(records)} rows to {csv_file}[/green]")
    else:
        print(json.dumps(data, indent=2))


def get_query_string(query: Optional[str], file: Optional[str], default_ext: str) -> str:
    if file:
        p = Path(file)
        if not p.exists():
            p_queries = Path("queries") / file
            if p_queries.exists():
                p = p_queries
            else:
                console.print(f"[bold red]Error:[/bold red] File '{file}' not found.")
                raise typer.Exit(1)
        return p.read_text().strip()
    if query:
        return query.strip()
    console.print("[bold red]Error:[/bold red] Must provide either a query string or --file.")
    raise typer.Exit(1)


def save_query_to_file(query_str: str, save_path: str, default_ext: str):
    p = Path(save_path)
    if not p.suffix:
        p = p.with_suffix(default_ext)
    if p.parent == Path("."):
        queries_dir = Path("queries")
        queries_dir.mkdir(exist_ok=True)
        p = queries_dir / p
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(query_str)
    console.print(f"[green]✓ Saved query to {p}[/green]")


@requires_auth
def sql(
    query: Optional[str] = typer.Argument(None, help="The SQL query string to execute."),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to a .sql file to execute."),
    hydrate: bool = typer.Option(
        False,
        "--hydrate",
        help="Hydrate lookup fields into {id, name} objects (default: off, returning raw string IDs).",
    ),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Maximum number of rows to return."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass server query cache."),
    save: Optional[str] = typer.Option(None, "--save", "-s", help="Save the query to a file (defaults to queries/<name>.sql)."),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save JSON output to a file."),
    csv_file: Optional[str] = typer.Option(None, "--csv", help="Export output directly to a CSV file."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Execute a SQL query against Valstorm.

    Returns raw lookup IDs by default. Pass `--hydrate` to expand lookup fields into `{id, name}` objects.
    """
    query_str = get_query_string(query, file, ".sql")
    if save:
        save_query_to_file(query_str, save, ".sql")

    try:
        data = sdk.query.sql(query_str, limit=limit, hydrate=hydrate, bypass_cache=no_cache)
        handle_query_save_and_output(data, output, save, csv_file)
    except ValstormError as e:
        console.print(f"[bold red]SQL Query failed:[/bold red] {e}")
        raise typer.Exit(1)


@requires_auth
def graphql(
    query: Optional[str] = typer.Argument(None, help="The GraphQL query string to execute."),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to a .graphql file to execute."),
    variables: Optional[str] = typer.Option(None, "--variables", "-v", help="JSON string of GraphQL variables."),
    hydrate: bool = typer.Option(
        False,
        "--hydrate",
        help="Preserve hydrated {id, name} lookup objects (default: off, unpacking nested lookups to raw IDs).",
    ),
    save: Optional[str] = typer.Option(None, "--save", "-s", help="Save the query to a file (defaults to queries/<name>.graphql)."),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save JSON output to a file."),
    csv_file: Optional[str] = typer.Option(None, "--csv", help="Export output directly to a CSV file."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Execute a GraphQL query against Valstorm.

    Unpacks nested `{id, name}` lookup objects to raw IDs by default. Pass `--hydrate` to keep `{id, name}`.
    """
    query_str = get_query_string(query, file, ".graphql")
    if save:
        save_query_to_file(query_str, save, ".graphql")

    parsed_vars = None
    if variables:
        try:
            parsed_vars = json.loads(variables)
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Invalid JSON in --variables:[/bold red] {e}")
            raise typer.Exit(1)

    try:
        data = sdk.query.graphql(query_str, variables=parsed_vars)
        if not hydrate:
            data = strip_hydrated_graphql_response(data)
        handle_query_save_and_output(data, output, save, csv_file)
    except ValstormError as e:
        console.print(f"[bold red]GraphQL Query failed:[/bold red] {e}")
        raise typer.Exit(1)
