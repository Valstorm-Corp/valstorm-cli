import typer
import httpx
import json
import csv
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from .auth import ValstormAuth

console = Console()
query_app = typer.Typer(help="Execute Queries", no_args_is_help=True)

def handle_query_save_and_output(data, output: str, save: Optional[str], csv_file: Optional[str]):
    if save:
        with open(save, 'w') as f:
            json.dump(data, f, indent=4)
        console.print(f"[green]✓ Results saved to {save}[/green]")
        
    if csv_file:
        if isinstance(data, list) and len(data) > 0:
            keys = data[0].keys()
            with open(csv_file, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(data)
            console.print(f"[green]✓ Results saved to {csv_file}[/green]")
        elif isinstance(data, dict):
            keys = data.keys()
            with open(csv_file, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerow(data)
            console.print(f"[green]✓ Results saved to {csv_file}[/green]")
        else:
            console.print("[yellow]Cannot save non-list/dict data as CSV.[/yellow]")

    if output == "json":
        console.print_json(data=data)
    else:
        if not data:
            console.print("[yellow]No records found.[/yellow]")
            return
        
        table = Table(show_header=True, header_style="bold magenta")
        
        # Get columns from first record
        if isinstance(data, list) and len(data) > 0:
            columns = data[0].keys()
            for col in columns:
                table.add_column(col)
                
            for row in data:
                table.add_row(*[str(row.get(col, "")) for col in columns])
            
            console.print(table)
            console.print(f"\n[dim]Total records: {len(data)}[/dim]")
        elif isinstance(data, dict):
            columns = data.keys()
            for col in columns:
                table.add_column(col)
            table.add_row(*[str(data.get(col, "")) for col in columns])
            console.print(table)
        else:
            console.print(data)

def get_query_string(query: Optional[str], file: Optional[str]) -> str:
    if file:
        try:
            with open(file, 'r') as f:
                return f.read().strip()
        except Exception as e:
            console.print(f"[bold red]Failed to read query file:[/bold red] {e}")
            raise typer.Exit(1)
    elif query:
        return query
    else:
        console.print("[bold red]Must provide either a query string or --file.[/bold red]")
        raise typer.Exit(1)

def save_query_to_file(query_str: str, file_path: str):
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(query_str)
        console.print(f"[green]✓ Query saved to {file_path}[/green]")
    except Exception as e:
        console.print(f"[bold red]Failed to save query file:[/bold red] {e}")

@query_app.command(name="sql")
def sql(
    query: Optional[str] = typer.Argument(None, help="The SQL query to execute."),
    file: Optional[str] = typer.Option(None, "--file", help="Execute query from file."),
    save_query: Optional[str] = typer.Option(None, "--save-query", help="Save the query itself to a file."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    output: str = typer.Option("table", "--output", "-o", help="Output format (table, json)."),
    bypass_cache: bool = typer.Option(False, "--bypass-cache", help="Bypass the query cache."),
    save: Optional[str] = typer.Option(None, "--save", "-s", help="Save results to a JSON file."),
    csv_file: Optional[str] = typer.Option(None, "--csv", help="Save results to a CSV file.")
):
    """Execute a SQL-like query against the Valstorm API."""
    query_str = get_query_string(query, file)
    
    if save_query:
        save_query_to_file(query_str, save_query)
        
    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        try:
            response = client.post("/query", json={
                "query": query_str,
                "bypass_cache": bypass_cache
            })
            
            if response.status_code != 200:
                console.print(f"[bold red]Query failed ({response.status_code}):[/bold red] {response.text}")
                raise typer.Exit(1)
                
            data = response.json()
            handle_query_save_and_output(data, output, save, csv_file)
                    
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

@query_app.command(name="graphql")
def graphql(
    query: Optional[str] = typer.Argument(None, help="The GraphQL query to execute."),
    file: Optional[str] = typer.Option(None, "--file", help="Execute query from file."),
    save_query: Optional[str] = typer.Option(None, "--save-query", help="Save the query itself to a file."),
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment."),
    output: str = typer.Option("json", "--output", "-o", help="Output format (table, json)."),
    save: Optional[str] = typer.Option(None, "--save", "-s", help="Save results to a JSON file."),
    csv_file: Optional[str] = typer.Option(None, "--csv", help="Save results to a CSV file.")
):
    """Execute a GraphQL query against the Valstorm API."""
    query_str = get_query_string(query, file)
    
    if save_query:
        save_query_to_file(query_str, save_query)
        
    auth = ValstormAuth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    with auth.get_client() as client:
        try:
            response = client.post("/graphql", json={
                "query": query_str
            })
            
            if response.status_code != 200:
                console.print(f"[bold red]GraphQL Query failed ({response.status_code}):[/bold red] {response.text}")
                raise typer.Exit(1)
                
            data = response.json()
            handle_query_save_and_output(data, output, save, csv_file)
                    
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)
