import typer
import httpx
import json
import sys
from rich.console import Console
from rich.table import Table
from typing import Optional

from .auth import get_auth, get_api_base_url

vfs_app = typer.Typer(help="Manage the Virtual File System (VFS)", no_args_is_help=True)
console = Console()

def handle_error(response: httpx.Response, json_output: bool):
    """Handles error reporting uniformly for VFS commands."""
    if response.status_code >= 400:
        if json_output:
            print(json.dumps({"error": response.text, "status_code": response.status_code}))
        else:
            console.print(f"[bold red]API Error ({response.status_code}):[/bold red] {response.text}")
        
        if response.status_code in (401, 403):
            sys.exit(3)
        elif response.status_code == 404:
            sys.exit(4)
        else:
            sys.exit(2)

@vfs_app.command("list")
def vfs_list(
    vault_id: Optional[str] = typer.Argument(None, help="Vault ID or Vault Name"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a formatted table"),
):
    """List files and directories in a given vault."""
    if not vault_id:
        vault_id = "root"
    auth = get_auth()
    base_url = get_api_base_url()
    
    with httpx.Client() as client:
        try:
            res = client.get(
                f"{base_url}/vfs/vault/{vault_id}",
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    # Rich output
    console.print(f"\n[bold]Contents of Vault:[/bold] {vault_id}\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="dim")
    table.add_column("Name")
    table.add_column("ID", style="cyan")

    for folder in data.get("folders", []):
        table.add_row("Directory", folder.get("name", "Unknown"), folder.get("id", ""))
        
    for f in data.get("files", []):
        table.add_row("File", f.get("name", "Unknown"), f.get("id", ""))

    console.print(table)


@vfs_app.command("query")
def vfs_query(
    query: str = typer.Option(..., "--query", help="SQL query string to search VFS metadata"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a formatted table"),
):
    """Query VFS metadata using a SQL-like syntax."""
    auth = get_auth()
    base_url = get_api_base_url()
    
    payload = {"query": query}

    with httpx.Client() as client:
        try:
            res = client.post(
                f"{base_url}/vfs/query",
                json=payload,
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    # Rich output
    if not data:
        console.print("[yellow]No results found.[/yellow]")
        return
        
    console.print(f"\n[bold]Query Results:[/bold]\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    if data and isinstance(data, list) and len(data) > 0:
        keys = list(data[0].keys())
        for k in keys[:5]: # Cap columns to prevent terminal explosion
            table.add_column(k)
            
        for row in data:
            row_data = [str(row.get(k, "")) for k in keys[:5]]
            table.add_row(*row_data)

    console.print(table)


@vfs_app.command("move")
def vfs_move(
    item_id: str = typer.Argument(..., help="The ID of the file or vault to move"),
    from_vault_id: str = typer.Option(..., help="The ID of the source vault"),
    to_vault_id: str = typer.Option(..., help="The ID of the destination vault"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a message"),
):
    """Move an item (vault or file) from one vault to another."""
    auth = get_auth()
    base_url = get_api_base_url()
    
    payload = {
        "item_id": item_id,
        "from_vault_id": from_vault_id,
        "to_vault_id": to_vault_id
    }

    with httpx.Client() as client:
        try:
            res = client.post(
                f"{base_url}/vfs/move",
                json=payload,
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    console.print(f"[green]Successfully moved item {item_id} to vault {to_vault_id}[/green]")

@vfs_app.command("upload")
def vfs_upload():
    """(Stub) Upload a file to VFS/S3"""
    console.print("Upload not implemented yet.")
    sys.exit(1)

@vfs_app.command("download")
def vfs_download():
    """(Stub) Download a file from VFS/S3"""
    console.print("Download not implemented yet.")
    sys.exit(1)

@vfs_app.command("delete")
def vfs_delete():
    """(Stub) Delete a file from VFS/S3"""
    console.print("Delete not implemented yet.")
    sys.exit(1)
