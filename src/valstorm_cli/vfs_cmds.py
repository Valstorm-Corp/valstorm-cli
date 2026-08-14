import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, NoReturn, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from .auth import requires_auth

vfs_app = typer.Typer(help="Manage the Virtual File System (VFS)", no_args_is_help=True)
console = Console()


def handle_error(response: httpx.Response, json_output: bool):
    """Handles error reporting uniformly for VFS commands."""
    if response.status_code >= 400:
        try:
            error_text = response.text
        except httpx.ResponseNotRead:
            response.read()
            error_text = response.text

        try:
            parsed_error = response.json()
        except Exception:
            parsed_error = error_text

        if json_output:
            print(json.dumps({"error": parsed_error, "status_code": response.status_code}))
        else:
            console.print(f"[bold red]API Error ({response.status_code}):[/bold red] {error_text}")

        if response.status_code in (401, 403):
            sys.exit(3)
        elif response.status_code == 404:
            sys.exit(4)
        else:
            sys.exit(2)


def handle_network_error(e: Exception, json_output: bool) -> NoReturn:
    """Handles network/request errors uniform reporting."""
    if json_output:
        print(json.dumps({"error": str(e), "status_code": 2}))
    else:
        console.print(f"[bold red]Network Error:[/bold red] {e}")
    sys.exit(2)


def handle_local_error(message: str, json_output: bool, exit_code: int = 1) -> NoReturn:
    """Handles local CLI validation errors uniform reporting."""
    if json_output:
        print(json.dumps({"error": message, "status_code": exit_code}))
    else:
        console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(exit_code)


@vfs_app.command("list")
@requires_auth
def vfs_list(
    vault_id: Optional[str] = typer.Argument(None, help="Vault ID, Vault Name, or String Path (e.g. /Marketing/Assets)"),
    bypass_cache: bool = typer.Option(False, "--bypass-cache", help="Bypass cache and query fresh data"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a formatted table"),
    client: httpx.Client = None,  # type: ignore
):
    """List files and directories in a given vault or path."""
    params = {"bypass_cache": "true" if bypass_cache else "false"}

    if not vault_id:
        try:
            res = client.get("/vfs/tree", params=params)
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            handle_network_error(e, json_output)

        if json_output:
            print(json.dumps(data, indent=2))
            return

        console.print("\n[bold]Virtual File System (VFS) Vault Tree[/bold]\n")

        vaults = data.get("vaults", [])
        vaults_by_id = {v["id"]: v for v in vaults if isinstance(v, dict) and "id" in v}
        children_map = {}
        roots = []
        for v in vaults:
            if not isinstance(v, dict):
                continue
            pid = v.get("parent_vault")
            if not pid or pid not in vaults_by_id:
                roots.append(v)
            else:
                children_map.setdefault(pid, []).append(v)

        def add_node(tree_node, vault):
            v_name = vault.get("name", "Unknown")
            v_id = vault.get("id", "")
            paths = vault.get("vault_paths", [])
            path_str = f" ({paths[0]})" if paths else ""
            node = tree_node.add(f"[cyan]📁 {v_name}[/cyan] [dim]{v_id}[/dim]{path_str}")
            for child in children_map.get(v_id, []):
                add_node(node, child)

        tree = Tree("Root")
        for root in roots:
            add_node(tree, root)

        console.print(tree)
        return

    try:
        if vault_id.startswith("/"):
            clean_path = vault_id.lstrip("/")
            res = client.get(f"/vfs/path/{clean_path}", params=params)
        else:
            res = client.get(f"/vfs/vault/{vault_id}", params=params)
        handle_error(res, json_output)
        data = res.json()
    except httpx.RequestError as e:
        handle_network_error(e, json_output)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    display_id = data.get("vault_id", vault_id)
    console.print(f"\n[bold]Contents of Vault/Path:[/bold] {display_id}\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="dim")
    table.add_column("Name")
    table.add_column("ID", style="cyan")

    for folder in data.get("folders", []):
        table.add_row("Directory", folder.get("name", "Unknown"), folder.get("id", ""))

    for f in data.get("files", []):
        table.add_row("File", f.get("name", "Unknown"), f.get("id", ""))

    console.print(table)


@vfs_app.command("resolve")
@requires_auth
def vfs_resolve(
    path: str = typer.Argument(..., help="String path e.g. /Marketing/Assets/logo.png"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
    client: httpx.Client = None,  # type: ignore
):
    """Resolves a string path to its VFS entity (Vault or File metadata)."""
    clean_path = path.lstrip("/")
    try:
        res = client.get(f"/vfs/path/{clean_path}")
        handle_error(res, json_output)
        data = res.json()
    except httpx.RequestError as e:
        handle_network_error(e, json_output)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    console.print(f"\n[bold]Resolved Path:[/bold] {path}\n")
    if isinstance(data, dict):
        if "folders" in data or "files" in data:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Type", style="dim")
            table.add_column("Name")
            table.add_column("ID", style="cyan")

            for folder in data.get("folders", []):
                table.add_row("Directory", folder.get("name", "Unknown"), folder.get("id", ""))

            for f in data.get("files", []):
                table.add_row("File", f.get("name", "Unknown"), f.get("id", ""))

            console.print(table)
        else:
            for k, v in data.items():
                console.print(f"[bold]{k}:[/bold] {v}")
    else:
        console.print(data)


@vfs_app.command("snapshot")
@requires_auth
def vfs_snapshot(
    bypass_cache: bool = typer.Option(False, "--bypass-cache", help="Force rebuild of snapshot"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
    client: httpx.Client = None,  # type: ignore
):
    """Download and display the entire VFS tree snapshot instantly."""
    start_time = time.time()
    params = {"bypass_cache": "true" if bypass_cache else "false"}
    try:
        res = client.get("/vfs/snapshot", params=params)
        handle_error(res, json_output)
        data = res.json()
    except httpx.RequestError as e:
        handle_network_error(e, json_output)

    elapsed = time.time() - start_time

    if json_output:
        print(json.dumps(data, indent=2))
        return

    vaults = data.get("vaults", [])
    files = data.get("files", [])

    vaults_map = {v["id"]: v for v in vaults if isinstance(v, dict) and "id" in v}
    vault_children = {}
    roots = []
    for v in vaults:
        if not isinstance(v, dict):
            continue
        pid = v.get("parent_vault")
        if not pid or pid not in vaults_map:
            roots.append(v)
        else:
            vault_children.setdefault(pid, []).append(v)

    vault_files = {}
    unassigned_files = []
    for f in files:
        if not isinstance(f, dict):
            continue
        v_list = f.get("vaults")
        if not v_list and f.get("parent_vault"):
            v_list = [f.get("parent_vault")]
        if v_list and isinstance(v_list, list):
            for vid in v_list:
                vault_files.setdefault(vid, []).append(f)
        else:
            unassigned_files.append(f)

    tree = Tree("[bold cyan]Virtual File System Snapshot[/bold cyan]")

    def render_vault(node, vault):
        v_id = vault.get("id", "")
        v_name = vault.get("name", "Unknown Vault")
        v_paths = vault.get("vault_paths", [])
        path_str = f" [dim]({v_paths[0]})[/dim]" if v_paths else ""
        vault_node = node.add(f"[cyan]📁 {v_name}[/cyan] [dim]({v_id})[/dim]{path_str}")

        for f in vault_files.get(v_id, []):
            f_name = f.get("name", "Unknown File")
            f_id = f.get("id", "")
            vault_node.add(f"[green]📄 {f_name}[/green] [dim]({f_id})[/dim]")

        for child in vault_children.get(v_id, []):
            render_vault(vault_node, child)

    for root in roots:
        render_vault(tree, root)

    if unassigned_files:
        unassigned_node = tree.add("[yellow]Unassigned Files[/yellow]")
        for f in unassigned_files:
            unassigned_node.add(f"[green]📄 {f.get('name', 'Unknown')}[/green] [dim]({f.get('id', '')})[/dim]")

    console.print(tree)
    console.print(f"\n[dim]Fetched {len(vaults)} vaults and {len(files)} files in {elapsed:.2f}s[/dim]")


@vfs_app.command("batch-vaults")
@requires_auth
def vfs_batch_vaults(
    vault_ids: List[str] = typer.Argument(..., help="Multiple Vault IDs to fetch"),
    bypass_cache: bool = typer.Option(False, "--bypass-cache", help="Bypass cache"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
    client: httpx.Client = None,  # type: ignore
):
    """Fetch contents of multiple vaults in a single request."""
    payload = {
        "vault_ids": vault_ids,
        "bypass_cache": bypass_cache,
    }
    try:
        res = client.post("/vfs/vaults/batch", json=payload)
        handle_error(res, json_output)
        data = res.json()
    except httpx.RequestError as e:
        handle_network_error(e, json_output)

    failed_count = sum(1 for vid, content in data.items() if isinstance(content, dict) and "error" in content)

    if json_output:
        print(json.dumps(data, indent=2))
        if failed_count > 0:
            sys.exit(5)
        return

    for vid, content in data.items():
        console.print(f"\n[bold magenta]Vault ID:[/bold magenta] [cyan]{vid}[/cyan]")
        if isinstance(content, dict) and "error" in content:
            console.print(f"[bold red]Error:[/bold red] {content['error']}")
            continue

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Type", style="dim")
        table.add_column("Name")
        table.add_column("ID", style="cyan")

        for folder in content.get("folders", []):
            table.add_row("Directory", folder.get("name", "Unknown"), folder.get("id", ""))

        for f in content.get("files", []):
            table.add_row("File", f.get("name", "Unknown"), f.get("id", ""))

        console.print(table)

    if failed_count > 0:
        sys.exit(5)


@vfs_app.command("batch-move")
@requires_auth
def vfs_batch_move(
    items: List[str] = typer.Argument(..., help="List of Item IDs (file_xxx or vaul_xxx) to move"),
    to_vault_id: str = typer.Option(..., "--to", help="Destination Vault ID"),
    from_vault_id: Optional[str] = typer.Option(None, "--from", help="Optional source Vault ID to remove from"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
    client: httpx.Client = None,  # type: ignore
):
    """Move multiple items into a destination vault simultaneously."""
    payload = {
        "items": [
            {
                "item_id": item,
                "from_vault_id": from_vault_id,
                "to_vault_id": to_vault_id,
            }
            for item in items
        ]
    }
    try:
        res = client.post("/vfs/batch-move", json=payload)
        handle_error(res, json_output)
        data = res.json()
    except httpx.RequestError as e:
        handle_network_error(e, json_output)

    results = data.get("results", [])
    failed_items = [r for r in results if r.get("status") != "success"]

    if json_output:
        print(json.dumps(data, indent=2))
        if failed_items:
            sys.exit(5)
        return

    table = Table(title="Batch Move Results", show_header=True, header_style="bold magenta")
    table.add_column("Item ID", style="cyan")
    table.add_column("Status")
    table.add_column("Message")

    for r in results:
        status = r.get("status", "unknown")
        item_id = r.get("item_id", "")
        if status == "success":
            status_str = "[green]Success[/green]"
            msg = f"Moved to {to_vault_id}"
        else:
            status_str = "[red]Error[/red]"
            msg = r.get("error", "Failed to move")
        table.add_row(item_id, status_str, msg)

    console.print(table)

    if failed_items:
        sys.exit(5)


@vfs_app.command("query")
@requires_auth
def vfs_query(
    query: str = typer.Option(..., "--query", help="SQL query string to search VFS metadata"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a formatted table"),
    client: httpx.Client = None,  # type: ignore
):
    """Query VFS metadata using a SQL-like syntax."""
    payload = {"query": query}

    try:
        res = client.post("/vfs/query", json=payload)
        handle_error(res, json_output)
        data = res.json()
    except httpx.RequestError as e:
        handle_network_error(e, json_output)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    if not data:
        console.print("[yellow]No results found.[/yellow]")
        return

    console.print("\n[bold]Query Results:[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    if data and isinstance(data, list) and len(data) > 0:
        keys = list(data[0].keys())
        for k in keys[:5]:  # Cap columns to prevent terminal explosion
            table.add_column(k)

        for row in data:
            row_data = [str(row.get(k, "")) for k in keys[:5]]
            table.add_row(*row_data)

    console.print(table)


@vfs_app.command("move")
@requires_auth
def vfs_move(
    item_id: str = typer.Argument(..., help="The ID of the file or vault to move"),
    from_vault_id: str = typer.Option(..., "--from", help="The ID of the source vault"),
    to_vault_id: str = typer.Option(..., "--to", help="The ID of the destination vault"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a message"),
    client: httpx.Client = None,  # type: ignore
):
    """Move an item (vault or file) from one vault to another."""
    payload = {
        "item_id": item_id,
        "from_vault_id": from_vault_id,
        "to_vault_id": to_vault_id,
    }

    try:
        res = client.post("/vfs/move", json=payload)
        handle_error(res, json_output)
        data = res.json()
    except httpx.RequestError as e:
        handle_network_error(e, json_output)

    if json_output:
        print(json.dumps(data, indent=2))
        return

    console.print(f"[green]Successfully moved item {item_id} to vault {to_vault_id}[/green]")


@vfs_app.command("rebuild-cache")
@requires_auth
def vfs_rebuild_cache(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response"),
    client: httpx.Client = None,  # type: ignore
):
    """Rebuild the Virtual File System (VFS) cache from the source of truth."""
    if json_output:
        try:
            res = client.post("/vfs/cache/rebuild")
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            handle_network_error(e, json_output)
        print(json.dumps(data, indent=2))
        return

    with console.status("[bold cyan]Rebuilding VFS cache...[/bold cyan]"):
        try:
            res = client.post("/vfs/cache/rebuild")
            handle_error(res, json_output)
            data = res.json()
        except httpx.RequestError as e:
            handle_network_error(e, json_output)

    msg = data.get("message", "VFS cache rebuilt successfully.") if isinstance(data, dict) else "VFS cache rebuilt successfully."
    console.print(f"[green]{msg}[/green]")


@vfs_app.command("upload")
@requires_auth
def vfs_upload(
    local_path: Path = typer.Argument(..., exists=True, help="Local file or directory path"),
    to_vault_id: str = typer.Option(..., "--to", help="Target VFS Vault ID"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Upload directory recursively"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a message"),
    client: httpx.Client = None,  # type: ignore
):
    """Upload a file or directory to VFS/S3."""
    if local_path.is_dir():
        if not recursive:
            handle_local_error(
                f"'{local_path}' is a directory. Use -r / --recursive to upload recursively.",
                json_output,
                exit_code=1,
            )

        uploaded_files = []
        dir_vault_map = {str(local_path): to_vault_id}

        for root, dirs, files in os.walk(local_path):
            current_vault_id = dir_vault_map[root]

            # Ensure subdirectories exist as vaults
            if dirs:
                try:
                    res = client.get(f"/vfs/vault/{current_vault_id}")
                    handle_error(res, json_output)
                    existing_folders = {f["name"]: f["id"] for f in res.json().get("folders", []) if isinstance(f, dict)}
                except httpx.RequestError as e:
                    handle_network_error(e, json_output)

                for d in dirs:
                    sub_path = os.path.join(root, d)
                    if d in existing_folders:
                        dir_vault_map[sub_path] = existing_folders[d]
                    else:
                        try:
                            v_res = client.post("/object/vault", json=[{"name": d, "parent_vault": current_vault_id}])
                            handle_error(v_res, json_output)
                            v_data = v_res.json()
                            new_id = v_data[0]["id"] if isinstance(v_data, list) and len(v_data) > 0 else v_data.get("id")
                            dir_vault_map[sub_path] = new_id
                        except httpx.RequestError as e:
                            handle_network_error(e, json_output)

            # Upload files in current directory
            for f in files:
                f_path = os.path.join(root, f)
                try:
                    with open(f_path, "rb") as fp:
                        res = client.post(
                            "/vfs/upload",
                            data={"vault_id": current_vault_id},
                            files={"file": (f, fp, "application/octet-stream")},
                        )
                        handle_error(res, json_output)
                        f_data = res.json()
                        uploaded_files.append({
                            "local_path": f_path,
                            "vault_id": current_vault_id,
                            "response": f_data,
                        })
                except httpx.RequestError as e:
                    handle_network_error(e, json_output)

        out_payload = {"uploaded": uploaded_files, "total": len(uploaded_files)}
        if json_output:
            print(json.dumps(out_payload, indent=2))
            return

        console.print(f"[green]Successfully recursively uploaded directory [bold]{local_path}[/bold] ({len(uploaded_files)} file(s)) to vault [bold]{to_vault_id}[/bold][/green]")
        return

    # Single file upload
    try:
        with open(local_path, "rb") as f:
            res = client.post(
                "/vfs/upload",
                data={"vault_id": to_vault_id},
                files={"file": (local_path.name, f, "application/octet-stream")},
            )
            handle_error(res, json_output)
            response_data = res.json()
    except httpx.RequestError as e:
        handle_network_error(e, json_output)

    if json_output:
        print(json.dumps(response_data, indent=2))
        return

    console.print(f"[green]Successfully uploaded [bold]{local_path.name}[/bold] to vault [bold]{to_vault_id}[/bold][/green]")
    if response_data.get("id"):
        console.print(f"File ID: [cyan]{response_data.get('id')}[/cyan]")


@vfs_app.command("download")
@requires_auth
def vfs_download(
    item_id: str = typer.Argument(..., help="File ID or Vault ID to download"),
    dest_path: Path = typer.Option(Path("."), "--dest", "-d", help="Local destination directory"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Download a vault recursively"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
    client: httpx.Client = None,  # type: ignore
):
    """Download a file or vault from VFS to local disk."""
    is_vault = item_id.startswith("vaul_")
    if not is_vault:
        try:
            check_res = client.get(f"/vfs/vault/{item_id}")
            if check_res.status_code == 200 and "folders" in check_res.json():
                is_vault = True
        except Exception:
            pass

    if is_vault:
        if not recursive:
            handle_local_error(
                f"'{item_id}' is a vault. Use -r / --recursive to download recursively.",
                json_output,
                exit_code=1,
            )

        downloaded_files = []

        def download_vault_recursively(v_id: str, local_dir: Path):
            local_dir.mkdir(parents=True, exist_ok=True)
            try:
                res = client.get(f"/vfs/vault/{v_id}")
                handle_error(res, json_output)
                v_data = res.json()
            except httpx.RequestError as e:
                handle_network_error(e, json_output)

            # Download files
            for file_rec in v_data.get("files", []):
                f_id = file_rec.get("id")
                f_name = file_rec.get("name") or f"downloaded_{f_id}"
                out_file = local_dir / f_name
                try:
                    with client.stream("GET", f"/vfs/download/{f_id}") as stream_res:
                        handle_error(stream_res, json_output)
                        with open(out_file, "wb") as fp:
                            for chunk in stream_res.iter_bytes(chunk_size=8192):
                                fp.write(chunk)
                        downloaded_files.append({"id": f_id, "local_path": str(out_file)})
                except httpx.RequestError as e:
                    handle_network_error(e, json_output)

            # Recursively download folders
            for folder_rec in v_data.get("folders", []):
                child_v_id = folder_rec.get("id")
                child_v_name = folder_rec.get("name", child_v_id)
                download_vault_recursively(child_v_id, local_dir / child_v_name)

        download_vault_recursively(item_id, dest_path)

        out_payload = {"downloaded": downloaded_files, "total": len(downloaded_files)}
        if json_output:
            print(json.dumps(out_payload, indent=2))
            return

        console.print(f"[green]Successfully downloaded vault [bold]{item_id}[/bold] ({len(downloaded_files)} file(s)) to [bold]{dest_path}[/bold][/green]")
        return

    # Single file download
    try:
        with client.stream("GET", f"/vfs/download/{item_id}") as res:
            handle_error(res, json_output)

            filename = f"downloaded_{item_id}"
            cd = res.headers.get("content-disposition")
            if cd:
                match = re.search(r'filename="?([^"]+)"?', cd)
                if match:
                    filename = match.group(1)

            if dest_path.is_dir():
                out_path = dest_path / filename
            else:
                out_path = dest_path

            out_path.parent.mkdir(parents=True, exist_ok=True)

            with open(out_path, "wb") as f:
                for chunk in res.iter_bytes(chunk_size=8192):
                    f.write(chunk)

            if json_output:
                print(json.dumps({"status": "success", "file_id": item_id, "saved_to": str(out_path)}, indent=2))
                return

            console.print(f"[green]Successfully downloaded to [bold]{out_path}[/bold][/green]")

    except httpx.RequestError as e:
        handle_network_error(e, json_output)


@vfs_app.command("delete")
@requires_auth
def vfs_delete(
    item_ids: List[str] = typer.Argument(..., help="Vault or File IDs to delete"),
    force: bool = typer.Option(False, "-f", "--force", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON instead of a message"),
    client: httpx.Client = None,  # type: ignore
):
    """Delete files or vaults from VFS."""
    if not force and not json_output:
        confirm = typer.confirm(f"Are you sure you want to delete {len(item_ids)} item(s)?")
        if not confirm:
            handle_local_error("Deletion cancelled.", json_output=False, exit_code=1)

    results = []
    failed_count = 0

    for item_id in item_ids:
        try:
            res = client.delete(f"/vfs/{item_id}")
            if res.status_code >= 400:
                failed_count += 1
                results.append({
                    "item_id": item_id,
                    "status": "error",
                    "status_code": res.status_code,
                    "error": res.text,
                })
            else:
                data = res.json() if res.status_code != 204 and res.text else {"message": "success"}
                results.append({
                    "item_id": item_id,
                    "status": "success",
                    "data": data,
                })
        except httpx.RequestError as e:
            failed_count += 1
            results.append({
                "item_id": item_id,
                "status": "error",
                "error": str(e),
            })

    output_data = {
        "results": results,
        "deleted_count": len(item_ids) - failed_count,
        "failed_count": failed_count,
    }

    if json_output:
        print(json.dumps(output_data, indent=2))
        if failed_count > 0:
            sys.exit(5 if failed_count < len(item_ids) else 2)
        return

    table = Table(title="Deletion Results", show_header=True, header_style="bold magenta")
    table.add_column("Item ID", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    for r in results:
        status_str = "[green]Success[/green]" if r["status"] == "success" else "[red]Error[/red]"
        details = "Deleted" if r["status"] == "success" else r.get("error", "Failed")
        table.add_row(r["item_id"], status_str, details)

    console.print(table)

    if failed_count > 0:
        sys.exit(5 if failed_count < len(item_ids) else 2)
