import json
import mimetypes
import sys
from pathlib import Path
from typing import List, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from .auth import requires_auth

console = Console()
vfs_app = typer.Typer(help="Manage files and vaults in the Valstorm Virtual File Service (VFS).")


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} PB"


def handle_error(res: httpx.Response, json_output: bool = False, action: str = "Request") -> None:
    if res.status_code < 400:
        return
    code = 1
    if res.status_code in (401, 403):
        code = 3
    elif res.status_code == 404:
        code = 4
    try:
        detail = res.json().get("detail", res.text)
    except Exception:
        detail = res.text
    if json_output:
        print(json.dumps({"error": action, "status_code": res.status_code, "detail": detail}, indent=2), file=sys.stderr)
    else:
        console.print(f"[bold red]{action} failed ({res.status_code}):[/bold red] {detail}")
    raise typer.Exit(code)


def handle_network_error(err: Exception, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps({"error": "Network error", "detail": str(err)}, indent=2), file=sys.stderr)
    else:
        console.print(f"[bold red]Network error:[/bold red] {err}")
    raise typer.Exit(2)


def handle_local_error(message: str, json_output: bool = False, exit_code: int = 1) -> None:
    if json_output:
        print(json.dumps({"error": message}, indent=2), file=sys.stderr)
    else:
        console.print(f"[bold red]Error:[/bold red] {message}")
    raise typer.Exit(exit_code)


def _handle_error(res: httpx.Response, json_output: bool, action: str) -> None:
    handle_error(res, json_output=json_output, action=action)


def _add_tree_nodes(tree_node: Tree, vaults: list) -> None:
    for v in vaults:
        if not isinstance(v, dict):
            continue
        vid = v.get("id", "")
        vname = v.get("name", "Unnamed")
        branch = tree_node.add(f"[bold cyan]{vname}[/bold cyan] [dim]({vid})[/dim]")
        children = v.get("children") or v.get("vaults") or []
        if children:
            _add_tree_nodes(branch, children)


@vfs_app.command("ls")
@requires_auth
def vfs_ls(
    target: Optional[str] = typer.Argument(
        None,
        help="Optional vault ID (vaul_...) or slash path (e.g. Finance/2026). Omit to list full vault tree.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    List vaults and files. Accepts a vault ID, a human path (e.g. `Finance/2026`), or no argument for the full vault tree.
    """
    if not target:
        res = client.get("/vfs/tree", timeout=30.0)
        if res.status_code != 200:
            _handle_error(res, json_output, "List VFS tree")
        data = res.json()
        if json_output:
            print(json.dumps(data, indent=2))
            return

        # Open Valstorm returns a list[dict]; legacy returned {"vaults": [...]}
        vaults = data if isinstance(data, list) else data.get("vaults", [])
        if not vaults:
            console.print("[yellow]No vaults found.[/yellow]")
            return
        tree = Tree("[bold]VFS Vaults[/bold]")
        _add_tree_nodes(tree, vaults)
        console.print(tree)
        return

    # Resolve path vs vault ID
    if target.startswith("vaul_") or target == "root":
        res = client.get(f"/vfs/vault/{target}", timeout=30.0)
        if res.status_code != 200:
            _handle_error(res, json_output, f"Inspect vault '{target}'")
        data = res.json()
    else:
        res = client.get("/vfs/resolve", params={"path": target}, timeout=30.0)
        if res.status_code != 200:
            _handle_error(res, json_output, f"Resolve path '{target}'")
        data = res.json()

    if json_output:
        print(json.dumps(data, indent=2))
        return

    child_vaults = data.get("vaults") or data.get("children") or []
    files = data.get("files") or []
    if not child_vaults and not files:
        # Single file resolved via path
        if data.get("id"):
            console.print(json.dumps(data, indent=2))
            return
        console.print(f"[yellow]Vault '{target}' is empty.[/yellow]")
        return

    table = Table(title=f"VFS: {data.get('name') or target}")
    table.add_column("Type", style="magenta", width=7)
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Size", justify="right", style="green")

    for v in child_vaults:
        if isinstance(v, dict):
            table.add_row("vault", str(v.get("id", "")), str(v.get("name", "")), "-")
    for f in files:
        if isinstance(f, dict):
            table.add_row(
                "file",
                str(f.get("id", "")),
                str(f.get("name") or f.get("file_name") or ""),
                _human_size(int(f.get("size_bytes") or f.get("size") or 0)),
            )
    console.print(table)


@vfs_app.command("info")
@requires_auth
def vfs_info(
    file_id: str = typer.Argument(..., help="File ID (e.g., file_123)."),
    versions: bool = typer.Option(False, "--versions", help="Also list file snapshot versions."),
    set_version: Optional[str] = typer.Option(None, "--set-version", help="Promote a specific version ID to active."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Inspect file metadata, list snapshot versions (`--versions`), or activate a version (`--set-version`).
    """
    clean_id = file_id.replace("cloud://", "").strip()

    if set_version:
        res = client.post(f"/files/{clean_id}/active-version/{set_version}", timeout=30.0)
        if res.status_code not in (200, 201):
            _handle_error(res, json_output, "Set active version")
        if json_output:
            print(json.dumps(res.json(), indent=2))
        else:
            console.print(f"[bold green]✓ Set active version of '{clean_id}' to '{set_version}'.[/bold green]")
        return

    res = client.get(f"/vfs/file/{clean_id}", timeout=30.0)
    if res.status_code != 200:
        _handle_error(res, json_output, f"Inspect file '{clean_id}'")
    data = res.json()

    if versions:
        v_res = client.get(f"/files/{clean_id}/versions", timeout=30.0)
        if v_res.status_code == 200:
            data = {"file": data, "versions": v_res.json()}

    print(json.dumps(data, indent=2))


@vfs_app.command("upload")
@requires_auth
def vfs_upload(
    local_path: Path = typer.Argument(..., help="Local file path to upload."),
    vault: Optional[str] = typer.Option(None, "--vault", "-v", help="Target vault ID (e.g. vaul_123)."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Override filename in VFS."),
    is_public: bool = typer.Option(False, "--public", help="Mark uploaded file as publicly readable."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Upload a local file into Valstorm VFS.
    """
    if not local_path.is_file():
        console.print(f"[bold red]Error:[/bold red] Local file not found: {local_path}")
        raise typer.Exit(1)

    upload_name = name or local_path.name
    content_type = mimetypes.guess_type(upload_name)[0] or "application/octet-stream"

    with open(local_path, "rb") as fh:
        files_param = {"file": (upload_name, fh, content_type)}
        form_data = {"is_public": str(is_public).lower()}
        if vault:
            form_data["vault_id"] = vault
        res = client.post("/vfs/upload", files=files_param, data=form_data, timeout=120.0)

    if res.status_code not in (200, 201):
        _handle_error(res, json_output, "Upload file")

    data = res.json()
    if json_output:
        print(json.dumps(data, indent=2))
        return

    file_id = data.get("id") or data.get("file_id") or ""
    console.print(f"[bold green]✓ Uploaded '{upload_name}'[/bold green] (ID: [cyan]{file_id}[/cyan])")


@vfs_app.command("download")
@requires_auth
def vfs_download(
    file_id: str = typer.Argument(..., help="File ID to download (e.g., file_123)."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Destination path (defaults to original filename)."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Download a file from Valstorm VFS to local disk.
    """
    clean_id = file_id.replace("cloud://", "").strip()
    dest = output
    if dest is None:
        meta_res = client.get(f"/vfs/file/{clean_id}", timeout=30.0)
        if meta_res.status_code == 200:
            meta = meta_res.json()
            dest = Path(meta.get("name") or meta.get("file_name") or f"{clean_id}.bin")
        else:
            dest = Path(f"{clean_id}.bin")

    res = client.get(f"/vfs/download/{clean_id}", timeout=120.0, follow_redirects=True)
    if res.status_code != 200:
        _handle_error(res, False, f"Download '{clean_id}'")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(res.content)
    console.print(f"[bold green]✓ Downloaded to {dest}[/bold green] ({_human_size(len(res.content))})")


@vfs_app.command("mv")
@requires_auth
def vfs_mv(
    item_ids: List[str] = typer.Argument(..., help="One or more file/vault IDs to move."),
    to: str = typer.Option(..., "--to", "-t", help="Target parent vault ID (or 'root')."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Move one or more files/vaults into a target vault.
    """
    target_vault = None if to == "root" else to
    if len(item_ids) == 1:
        item_id = item_ids[0].replace("cloud://", "").strip()
        item_type = "vault" if item_id.startswith("vaul_") else "file"
        res = client.post(
            "/vfs/move",
            json={"item_id": item_id, "item_type": item_type, "target_vault_id": target_vault},
            timeout=30.0,
        )
    else:
        items_payload = [
            {
                "item_id": i.replace("cloud://", "").strip(),
                "item_type": "vault" if i.startswith("vaul_") else "file",
                "target_vault_id": target_vault,
            }
            for i in item_ids
        ]
        res = client.post("/vfs/batch-move", json={"items": items_payload}, timeout=60.0)

    if res.status_code not in (200, 201):
        _handle_error(res, json_output, "Move VFS item(s)")

    if json_output:
        print(json.dumps(res.json(), indent=2))
        return
    console.print(f"[bold green]✓ Moved {len(item_ids)} item(s) to '{to}'.[/bold green]")


@vfs_app.command("rm")
@requires_auth
def vfs_rm(
    item_ids: List[str] = typer.Argument(..., help="One or more file or vault IDs to delete."),
    force: bool = typer.Option(False, "--force", "-y", help="Skip confirmation prompt."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Delete one or more files or vaults from VFS.
    """
    clean_ids = [i.replace("cloud://", "").strip() for i in item_ids]
    if not force:
        if not typer.confirm(f"Are you sure you want to delete {len(clean_ids)} VFS item(s)?"):
            console.print("Operation cancelled.")
            raise typer.Exit(0)

    if len(clean_ids) == 1:
        res = client.delete(f"/vfs/item/{clean_ids[0]}", timeout=30.0)
    else:
        res = client.post("/vfs/batch-delete", json={"items": clean_ids}, timeout=60.0)

    if res.status_code not in (200, 204):
        _handle_error(res, json_output, "Delete VFS item(s)")

    if json_output:
        print(json.dumps({"deleted": clean_ids}, indent=2))
        return
    console.print(f"[bold green]✓ Deleted {len(clean_ids)} item(s).[/bold green]")


@vfs_app.command("index")
@requires_auth
def vfs_index(
    file_id: Optional[str] = typer.Argument(None, help="File ID or VFS path (e.g. /Docs/report.pdf) to index (omit if using --vault or --all)."),
    vault: Optional[str] = typer.Option(None, "--vault", "-v", help="Batch-index all files in a vault ID."),
    all_files: bool = typer.Option(False, "--all", help="Batch-index all files in the organization."),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-indexing even if already indexed."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Index (or re-index with `--force`) a single file/path, a vault, or all organization files for hybrid search.
    """
    if file_id:
        clean_id = file_id.replace("cloud://", "").strip()
        if "/" in clean_id:
            res_resolve = client.get("/vfs/resolve", params={"path": clean_id}, timeout=30.0)
            if res_resolve.status_code != 200:
                _handle_error(res_resolve, json_output, f"Resolve path '{clean_id}'")
            resolved = res_resolve.json()
            clean_id = resolved.get("id") or clean_id
        res = client.post(f"/vfs/files/{clean_id}/index", json={"force": force}, timeout=60.0)
    elif vault or all_files:
        payload = {"force": force}
        if vault:
            payload["vault_id"] = vault
        res = client.post("/vfs/index/batch", json=payload, timeout=120.0)
    else:
        console.print("[bold red]Error:[/bold red] Specify a `file_id`, `--vault <id>`, or `--all`.")
        raise typer.Exit(1)

    if res.status_code not in (200, 201, 202):
        _handle_error(res, json_output, "Index VFS file(s)")

    data = res.json()
    if json_output:
        print(json.dumps(data, indent=2))
        return
    if file_id:
        console.print(f"[bold green]✓ Indexing task dispatched for file {clean_id}.[/bold green]")
    else:
        console.print("[bold green]✓ Batch indexing triggered successfully.[/bold green]")
