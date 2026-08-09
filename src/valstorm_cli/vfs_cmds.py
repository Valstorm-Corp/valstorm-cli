import json
import sys

import httpx
import typer
from rich.console import Console
from rich.table import Table

from .auth import get_api_base_url, get_auth

vfs_app = typer.Typer(help="Manage the Virtual File System (VFS)", no_args_is_help=True)
console = Console()

def handle_error(response: httpx.Response, json_output: bool):
    """Handles error reporting uniformly for VFS commands."""
    if response.status_code >= 400:
        # Check if response has been read (or is streaming)
        try:
            error_text = response.text
        except httpx.ResponseNotRead:
            response.read()
            error_text = response.text

        if json_output:
            print(json.dumps({"error": error_text, "status_code": response.status_code}))
        else:
            console.print(f"[bold red]API Error ({response.status_code}):[/bold red] {error_text}")
        
        if response.status_code in (401, 403):
            sys.exit(3)
        elif response.status_code == 404:
            sys.exit(4)
        else:
            sys.exit(2)

@vfs_app.command("list")
def vfs_list(
    vault_id: str | None = typer.Argument(None, help="Vault ID or Vault Name"),
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
        
    console.print("\n[bold]Query Results:[/bold]\n")
    
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

@vfs_app.command("rebuild-cache")
def vfs_rebuild_cache(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response"),
):
    """Rebuild the Virtual File System (VFS) cache from the source of truth."""
    auth = get_auth()
    base_url = get_api_base_url()

    if json_output:
        with httpx.Client() as client:
            try:
                res = client.post(
                    f"{base_url}/vfs/cache/rebuild",
                    headers={"Authorization": f"Bearer {auth.access_token}"}
                )
                handle_error(res, json_output)
                data = res.json()
            except httpx.RequestError as e:
                print(json.dumps({"error": str(e)}))
                sys.exit(2)
        print(json.dumps(data, indent=2))
        return

    with console.status("[bold cyan]Rebuilding VFS cache...[/bold cyan]"), httpx.Client() as client:
        try:
            res = client.post(
                f"{base_url}/vfs/cache/rebuild",
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    msg = data.get("message", "VFS cache rebuilt successfully.") if isinstance(data, dict) else "VFS cache rebuilt successfully."
    console.print(f"[green]{msg}[/green]")

@vfs_app.command("upload")
def vfs_upload(
    file_path: str = typer.Argument(..., help="Local path to the file to upload"),
    vault_id: str = typer.Argument(..., help="Destination Vault ID"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a message"),
):
    """Upload a file to VFS/S3"""
    import os
    auth = get_auth()
    base_url = get_api_base_url()
    
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        sys.exit(1)
        
    filename = os.path.basename(file_path)
    
    with httpx.Client(timeout=300.0) as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, "application/octet-stream")}
                data = {"vault_id": vault_id}
                
                res = client.post(
                    f"{base_url}/vfs/upload",
                    data=data,
                    files=files,
                    headers={"Authorization": f"Bearer {auth.access_token}"}
                )
                handle_error(res, json_output)
                response_data = res.json()
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)

    if json_output:
        print(json.dumps(response_data, indent=2))
        return

    console.print(f"[green]Successfully uploaded [bold]{filename}[/bold] to vault [bold]{vault_id}[/bold][/green]")
    if response_data.get("id"):
        console.print(f"File ID: [cyan]{response_data.get('id')}[/cyan]")


@vfs_app.command("download")
def vfs_download(
    file_id: str = typer.Argument(..., help="File ID to download"),
    destination_path: str | None = typer.Argument(None, help="Destination directory or file path"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON on error"),
):
    """Download a file from VFS/S3"""
    import os
    import re
    auth = get_auth()
    base_url = get_api_base_url()
    
    with httpx.Client(timeout=300.0) as client:
        try:
            with client.stream(
                "GET",
                f"{base_url}/vfs/download/{file_id}",
                headers={"Authorization": f"Bearer {auth.access_token}"}
            ) as res:
                handle_error(res, json_output)
                
                # Try to get filename from Content-Disposition
                filename = f"downloaded_{file_id}"
                cd = res.headers.get("content-disposition")
                if cd:
                    match = re.search(r'filename="?([^"]+)"?', cd)
                    if match:
                        filename = match.group(1)
                
                # Determine final output path
                out_path = filename
                if destination_path:
                    if os.path.isdir(destination_path):
                        out_path = os.path.join(destination_path, filename)
                    else:
                        out_path = destination_path
                
                # Stream to disk
                with open(out_path, "wb") as f:
                    for chunk in res.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        
                if not json_output:
                    console.print(f"[green]Successfully downloaded to [bold]{out_path}[/bold][/green]")
                    
        except httpx.RequestError as e:
            if json_output:
                print(json.dumps({"error": str(e)}))
            else:
                console.print(f"[bold red]Network Error:[/bold red] {e}")
            sys.exit(2)


@vfs_app.command("delete")
def vfs_delete(
    item_id: str = typer.Argument(..., help="Vault or File ID to delete"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a message"),
):
    """Delete a file or vault from VFS/S3"""
    auth = get_auth()
    base_url = get_api_base_url()

    with httpx.Client() as client:
        try:
            res = client.delete(
                f"{base_url}/vfs/{item_id}",
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
            handle_error(res, json_output)
            
            # 204 No Content doesn't have json
            if res.status_code == 204:
                data = {"message": "success"}
            else:
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

    console.print(f"[green]Successfully deleted [bold]{item_id}[/bold][/green]")
