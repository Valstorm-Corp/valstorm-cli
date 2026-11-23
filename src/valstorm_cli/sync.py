import json
from pathlib import Path
from typing import Any, List, Optional

import typer
from rich.console import Console
from rich.table import Table
from valstorm import ValstormClient, ValstormError

from .auth import find_project_root, load_config, requires_auth
from .git_utils import get_git_diff_files
from .manifest_builder import build_manifest_from_files

console = Console()

CODE_OBJECT_TYPES = {"function", "record_trigger", "api_trigger"}

DEFAULT_METADATA_FOLDERS = {
    "record_trigger": "record_trigger",
    "api_trigger": "api_trigger",
    "function": "function",
    "automation": "automation",
    "ai_agent": "ai_agent",
    "app": "app",
    "app_page": "app_page",
    "app_metadata": "app_metadata",
    "permission": "permission",
    "notification_setting": "notification_setting",
    "schedule_trigger_setting": "schedule_trigger_setting",
    "workspace": "workspace",
    "list_filter": "list_filter",
    "dashboard": "dashboard",
    "report": "report",
    "tag": "tag",
    "integrated_app": "integrated_app",
    "oauth_app": "oauth_app",
}


def _resolve_root() -> Path:
    root = find_project_root()
    if root:
        return root
    return Path.cwd()


def _load_local_metadata(root: Path) -> dict[str, Any]:
    meta_file = root / ".valstorm" / "metadata.json"
    if meta_file.exists():
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_local_metadata(root: Path, metadata: dict[str, Any]) -> None:
    meta_dir = root / ".valstorm"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _safe_filename(name: str, default_ext: str) -> str:
    clean = name.strip().replace("/", "_").replace("\\", "_")
    if not clean:
        clean = "unnamed"
    if not clean.endswith(default_ext):
        clean = f"{clean}{default_ext}"
    return clean


@requires_auth
def pull(
    types: Optional[List[str]] = typer.Option(
        None,
        "--type",
        "-t",
        help="Metadata object type(s) to pull (repeatable, e.g. -t function -t record_trigger). Defaults to all.",
    ),
    app_id: Optional[str] = typer.Option(None, "--app", "-a", help="Filter metadata and schemas by App ID."),
    file_name: Optional[str] = typer.Option(None, "--file-name", help="Pull a single record matching this file_name."),
    manifest: Optional[Path] = typer.Option(None, "--manifest", "-m", help="Pull only items specified in a manifest JSON file."),
    schemas_only: bool = typer.Option(False, "--schemas-only", help="Pull only object schemas into schemas/*.json."),
    no_schemas: bool = typer.Option(False, "--no-schemas", help="Skip pulling object schemas."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing local files without prompting."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Pull workspace metadata and object schemas in a single roundtrip via `/v1/apps/metadata/pull`.
    """
    root = _resolve_root()
    manifest_data = None
    if manifest:
        if not manifest.exists():
            console.print(f"[bold red]Error:[/bold red] Manifest file not found: {manifest}")
            raise typer.Exit(1)
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))

    object_types = [] if schemas_only else (list(types) if types else None)
    include_schemas = True if schemas_only else (not no_schemas)

    console.print("Pulling metadata from Open Valstorm...")
    try:
        res = sdk.apps.pull_metadata(
            object_types=object_types,
            file_name=file_name,
            app_id=app_id,
            manifest=manifest_data,
            include_schemas=include_schemas,
        )
    except ValstormError as e:
        console.print(f"[bold red]Pull failed:[/bold red] {e}")
        raise typer.Exit(1)

    local_meta = _load_local_metadata(root)
    files_written = 0
    schemas_written = 0

    # 1. Write schemas
    schemas_payload = res.get("schemas") or {}
    schema_items: list[tuple[str, dict[str, Any]]] = []
    if isinstance(schemas_payload, dict):
        schema_items = [(k, v) for k, v in schemas_payload.items() if isinstance(v, dict)]
    elif isinstance(schemas_payload, list):
        schema_items = [(str(s.get("api_name", "")), s) for s in schemas_payload if isinstance(s, dict) and s.get("api_name")]

    if schema_items:
        schemas_dir = root / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)
        for api_name, schema_doc in schema_items:
            target_file = schemas_dir / f"{api_name}.json"
            if target_file.exists() and not force:
                if not typer.confirm(f"Overwrite schema {target_file.relative_to(root)}?", default=True):
                    continue
            target_file.write_text(json.dumps(schema_doc, indent=2, default=str), encoding="utf-8")
            schemas_written += 1

    # 2. Write metadata objects
    objects_payload = res.get("objects") or {}
    if isinstance(objects_payload, dict) and not schemas_only:
        for obj_type, records in objects_payload.items():
            if not isinstance(records, list) or not records:
                continue
            target_dir = root / DEFAULT_METADATA_FOLDERS.get(obj_type, obj_type)
            target_dir.mkdir(parents=True, exist_ok=True)

            for rec in records:
                if not isinstance(rec, dict):
                    continue
                is_code = obj_type in CODE_OBJECT_TYPES or isinstance(rec.get("code"), str)
                raw_name = rec.get("file_name") or rec.get("name") or rec.get("slug") or rec.get("id") or "unnamed"
                ext = ".py" if is_code else ".json"
                fname = _safe_filename(str(raw_name), ext)
                target_file = target_dir / fname

                if target_file.exists() and not force:
                    if not typer.confirm(f"Overwrite {target_file.relative_to(root)}?", default=True):
                        continue

                if is_code:
                    target_file.write_text(str(rec.get("code") or ""), encoding="utf-8")
                    meta_entry = {k: v for k, v in rec.items() if k != "code"}
                    meta_entry["type"] = obj_type
                    meta_entry["file_name"] = fname
                    rel_key = str(target_file.relative_to(root))
                    local_meta[rel_key] = meta_entry
                else:
                    target_file.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
                    rel_key = str(target_file.relative_to(root))
                    local_meta[rel_key] = {
                        "id": rec.get("id"),
                        "type": obj_type,
                        "name": rec.get("name"),
                        "file_name": fname,
                    }
                files_written += 1

    if files_written:
        _save_local_metadata(root, local_meta)

    console.print(
        f"[bold green]✓ Pull complete![/bold green] Wrote [cyan]{schemas_written}[/cyan] schema(s) "
        f"and [cyan]{files_written}[/cyan] metadata file(s)."
    )


def _collect_push_payload(
    root: Path,
    target_path: Optional[Path],
    manifest_data: Optional[dict[str, Any]],
    schemas_only: bool,
    app_id: Optional[str],
) -> tuple[dict[str, Any], dict[str, Path]]:
    """
    Collects schemas and metadata objects from the workspace into a single payload
    compatible with `POST /v1/apps/metadata/push`.
    Returns `(payload, file_map)` where `file_map` maps `(obj_type, file_name)` keys to local Paths.
    """
    local_meta = _load_local_metadata(root)
    schemas_to_push: list[dict[str, Any]] = []
    objects_to_push: dict[str, list[dict[str, Any]]] = {}
    rel_paths_by_key: dict[str, Path] = {}

    manifest_schemas = set(manifest_data.get("schemas") or []) if manifest_data else None
    manifest_objects = manifest_data.get("objects") if manifest_data and isinstance(manifest_data.get("objects"), dict) else None

    # Determine explicit file list when targeting a single path
    explicit_files: Optional[list[Path]] = None
    if target_path is not None:
        resolved = target_path.resolve()
        if not resolved.exists():
            console.print(f"[bold red]Error:[/bold red] Path not found: {target_path}")
            raise typer.Exit(1)
        if resolved.is_file():
            explicit_files = [resolved]
        else:
            explicit_files = [p for p in resolved.rglob("*") if p.is_file() and p.suffix in (".py", ".json")]

    # 1. Collect schemas
    schemas_dir = root / "schemas"
    if schemas_dir.exists():
        for sf in sorted(schemas_dir.glob("*.json")):
            if explicit_files is not None and sf.resolve() not in {p.resolve() for p in explicit_files}:
                continue
            if manifest_schemas is not None and sf.stem not in manifest_schemas:
                continue
            try:
                schema_doc = json.loads(sf.read_text(encoding="utf-8"))
                if isinstance(schema_doc, dict):
                    schema_doc.setdefault("api_name", sf.stem)
                    schemas_to_push.append(schema_doc)
            except json.JSONDecodeError as e:
                console.print(f"[bold red]Invalid JSON in schema {sf.name}:[/bold red] {e}")
                raise typer.Exit(1)

    if schemas_only:
        payload: dict[str, Any] = {"schemas": schemas_to_push, "objects": {}}
        if app_id:
            payload["app_id"] = app_id
        return payload, rel_paths_by_key

    # 2. Collect metadata objects
    candidate_dirs = sorted([d for d in root.iterdir() if d.is_dir() and d.name in DEFAULT_METADATA_FOLDERS])
    for folder in candidate_dirs:
        obj_type = folder.name
        allowed_names = None
        if manifest_objects is not None:
            if obj_type not in manifest_objects:
                continue
            allowed_names = set(manifest_objects[obj_type] or [])

        for f in sorted(folder.rglob("*")):
            if not f.is_file() or f.suffix not in (".py", ".json"):
                continue
            if explicit_files is not None and f.resolve() not in {p.resolve() for p in explicit_files}:
                continue
            if allowed_names is not None and f.name not in allowed_names and f.stem not in allowed_names:
                continue

            rel_key = str(f.relative_to(root))
            tracked = local_meta.get(rel_key, {})

            if f.suffix == ".py":
                rec = dict(tracked)
                rec.pop("type", None)
                rec["code"] = f.read_text(encoding="utf-8")
                rec.setdefault("file_name", f.name)
                rec.setdefault("name", f.stem)
                if app_id and not rec.get("app"):
                    rec["app"] = app_id
            else:
                try:
                    rec = json.loads(f.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    console.print(f"[bold red]Invalid JSON in {rel_key}:[/bold red] {e}")
                    raise typer.Exit(1)
                if not isinstance(rec, dict):
                    continue
                if tracked.get("id") and not rec.get("id"):
                    rec["id"] = tracked["id"]
                rec.setdefault("file_name", f.name)
                if app_id and not rec.get("app"):
                    rec["app"] = app_id

            objects_to_push.setdefault(obj_type, []).append(rec)
            rel_paths_by_key[f"{obj_type}:{rec.get('file_name', f.name)}"] = f

    payload = {"schemas": schemas_to_push, "objects": objects_to_push}
    if app_id:
        payload["app_id"] = app_id
    return payload, rel_paths_by_key


@requires_auth
def push(
    path: Optional[Path] = typer.Argument(None, help="Optional file or folder to push (defaults to whole workspace)."),
    manifest: Optional[Path] = typer.Option(None, "--manifest", "-m", help="Push only items listed in a manifest JSON file."),
    diff: Optional[str] = typer.Option(None, "--diff", "-d", help="Push only files changed relative to a git ref (e.g. origin/main)."),
    schemas_only: bool = typer.Option(False, "--schemas-only", help="Push only object schemas from schemas/*.json."),
    app_id: Optional[str] = typer.Option(None, "--app", "-a", help="Optional App ID to associate with newly created records."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview schemas and records that would be pushed without modifying the server."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON response."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Push local metadata and schemas atomically in a single ACID transaction via `/v1/apps/metadata/push`.
    """
    root = _resolve_root()
    if app_id is None:
        cfg_file = root / "valstorm.json"
        if cfg_file.exists():
            try:
                cfg = load_config(root)
                app_id = cfg.get("app_id")
            except Exception:
                pass

    manifest_data = None
    if manifest:
        if not manifest.exists():
            console.print(f"[bold red]Error:[/bold red] Manifest file not found: {manifest}")
            raise typer.Exit(1)
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    elif diff:
        changed = get_git_diff_files(diff)
        if not changed:
            console.print(f"[yellow]No changed files detected relative to '{diff}'.[/yellow]")
            return
        manifest_data = build_manifest_from_files(changed, root)

    payload, rel_paths_by_key = _collect_push_payload(
        root=root,
        target_path=path,
        manifest_data=manifest_data,
        schemas_only=schemas_only,
        app_id=app_id,
    )

    schema_count = len(payload["schemas"])
    record_count = sum(len(v) for v in payload["objects"].values())
    if schema_count == 0 and record_count == 0:
        console.print("[yellow]Nothing to push.[/yellow]")
        return

    if dry_run:
        table = Table(title="Dry-Run Push Summary")
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Items")
        if schema_count:
            table.add_row("schemas", str(schema_count), ", ".join(s.get("api_name", "") for s in payload["schemas"]))
        for obj_type, recs in payload["objects"].items():
            table.add_row(obj_type, str(len(recs)), ", ".join(str(r.get("file_name") or r.get("name") or r.get("id") or "") for r in recs))
        console.print(table)
        return

    console.print(f"Pushing [cyan]{schema_count}[/cyan] schema(s) and [cyan]{record_count}[/cyan] metadata record(s)...")
    try:
        res = sdk.apps.push_metadata(payload)
    except ValstormError as e:
        console.print(f"[bold red]Push failed:[/bold red] {e}")
        raise typer.Exit(1)

    # Persist any server-assigned IDs back into .valstorm/metadata.json
    pushed_objects = res.get("objects") or {}
    if isinstance(pushed_objects, dict) and pushed_objects:
        local_meta = _load_local_metadata(root)
        for obj_type, recs in pushed_objects.items():
            if not isinstance(recs, list):
                continue
            for rec in recs:
                if not isinstance(rec, dict):
                    continue
                fname = rec.get("file_name")
                local_path = rel_paths_by_key.get(f"{obj_type}:{fname}")
                if local_path:
                    rel_key = str(local_path.relative_to(root))
                    entry = {k: v for k, v in rec.items() if k != "code"}
                    entry["type"] = obj_type
                    local_meta[rel_key] = entry
        _save_local_metadata(root, local_meta)

    if json_output:
        print(json.dumps(res, indent=2))
        return

    console.print(
        f"[bold green]✓ Push completed![/bold green] "
        f"Schemas: [cyan]{res.get('schemas_pushed', schema_count)}[/cyan], "
        f"Created: [green]{res.get('created_count', 0)}[/green], "
        f"Updated: [blue]{res.get('updated_count', 0)}[/blue]."
    )
