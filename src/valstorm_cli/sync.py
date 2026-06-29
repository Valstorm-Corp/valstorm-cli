import typer
import json
from typing import Optional
from pathlib import Path
from rich.console import Console
from .auth import get_auth, get_api_base_url, get_project_root
from .scaffold import prepare_web_push
from .project import update_local_stubs

console = Console()
pull_app = typer.Typer(help="Download assets from the Valstorm cloud.")
push_app = typer.Typer(help="Upload local changes to the Valstorm cloud.")





@pull_app.command(name="metadata")
def pull(
    object_type: str = typer.Argument(None, help="Specific object type to pull (e.g., record_trigger)."),
    file_name: str = typer.Argument(None, help="Specific file to pull (e.g., trigger_name.py)."),
    manifest: str = typer.Option(None, "--manifest", "-m", help="Path to a deployment manifest JSON file."),
    force: bool = typer.Option(False, "--force", "--yes", "-y", help="Overwrite local changes without asking."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Download records for metadata objects from the Valstorm cloud.
    """
    root = get_project_root()
    
    # Auto-update stubs silently on pull
    update_local_stubs(root, silent=True)
    
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    # 1. Fetch available schemas to see what we can pull
    with auth.get_client() as client:
        schema_res = client.get("/schema")
        if schema_res.status_code != 200:
            console.print("[bold red]Failed to fetch schemas.[/bold red]")
            raise typer.Exit(1)
        available_schemas = schema_res.json()

    # 2. Define target types
    manifest_data = None
    if manifest:
        manifest_path = Path(manifest)
        if not manifest_path.exists():
            console.print(f"[bold red]Manifest file not found:[/bold red] {manifest}")
            raise typer.Exit(1)
        with open(manifest_path, "r") as f:
            manifest_data = json.load(f).get("objects", {})
        target_types = [t for t in manifest_data.keys() if t in available_schemas]
    elif object_type:
        if object_type not in available_schemas:
            console.print(f"[bold red]Error:[/bold red] Object type '{object_type}' not found in schemas.")
            raise typer.Exit(1)
        target_types = [object_type]
    else:
        try:
            with open(root / "valstorm.json", "r") as f:
                config = json.load(f)
        except Exception:
            config = {}
            
        configured_objects = config.get("objects")
        
        if configured_objects:
            target_types = [t for t in configured_objects if t in available_schemas]
        else:
            core_types = ["record_trigger", "function"]
            metadata_types = [
                "ai_agent", "app", "app_page", "app_metadata", 
                "permission", "notification_setting", 
                "schedule_trigger_setting", "workspace"
            ]
            target_types = [t for t in (core_types + metadata_types) if t in available_schemas]
    
    if not target_types:
        console.print("[yellow]No matching objects found in schemas to pull records for.[/yellow]")
    
    for file_type in target_types:
        console.print(f"Pulling [cyan]{file_type}[/cyan]s from [blue]{get_api_base_url(auth.env)}[/blue]...")
        query = f"SELECT * FROM {file_type}"
        if manifest_data and file_type in manifest_data:
            files_to_pull = manifest_data[file_type]
            if isinstance(files_to_pull, list) and files_to_pull:
                conditions = " OR ".join([f"file_name = '{f}'" for f in files_to_pull])
                query += f" WHERE ({conditions})"
            elif isinstance(files_to_pull, list) and not files_to_pull:
                continue
        elif file_name:
            query += f" WHERE file_name = '{file_name}'"
        
        with auth.get_client() as client:
            response = client.post("/query", json={"query": query})
            
            if response.status_code != 200:
                console.print(f"[bold red]Fetch failed for {file_type}:[/bold red] {response.status_code}")
                continue
                
            data = response.json()
            records = data.get("data", data) if isinstance(data, dict) else data
            
            if not isinstance(records, list):
                console.print(f"[yellow]No records found for {file_type}.[/yellow]")
                continue
                
            if file_name:
                records = [r for r in records if r.get("file_name") == file_name]

            target_dir = root / "object" / file_type
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Clean up old monolithic metadata file if it exists
            old_meta = target_dir / f"{file_type}_metadata.json"
            if old_meta.exists():
                try:
                    old_meta.unlink()
                except Exception:
                    pass

            count = 0
            code_count = 0
            for record in records:
                count += 1
                
                # Save individual metadata
                safe_name = "".join(c for c in str(record.get("name", "unnamed")) if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
                record_id = record.get("id", "noid")
                
                with open(target_dir / f"{safe_name}_{record_id}.json", "w") as f:
                    json.dump(record, f, indent=4)
                file_name = record.get("file_name")
                code = record.get("code")
                
                if file_name and code:
                    file_path = target_dir / file_name
                    
                    # Check if local file exists and has different content
                    if file_path.exists() and not force:
                        with open(file_path, "r") as f:
                            local_code = f.read()
                        if local_code != code:
                            choice = typer.prompt(
                                f"Local changes detected in {file_name}. Overwrite? [y/N/a] (a=all)",
                                default="n"
                            ).lower()
                            
                            if choice == 'a':
                                force = True
                            elif choice != 'y':
                                console.print(f"Skipping {file_name}")
                                continue
                    
                    with open(file_path, "w") as f:
                        f.write(code)
                    code_count += 1
            
            if code_count > 0:
                console.print(f"[green]✓[/green] Synchronized {count} {file_type} records ({code_count} files).")
            else:
                console.print(f"[green]✓[/green] Synchronized {count} {file_type} records.")
    
    # Also pull schema definitions
    try:
        pull_schemas(object_type=object_type, profile=profile, env=env)
    except Exception as e:
        console.print(f"[yellow]![/yellow] Warning: Failed to pull schemas during pull: {e}")

@pull_app.command(name="schemas")
def pull_schemas(
    object_type: str = typer.Argument(None, help="Specific object schema to pull."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Download object schemas from the Valstorm cloud.
    """
    root = get_project_root()
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    console.print(f"Pulling [cyan]schemas[/cyan] from [blue]{get_api_base_url(auth.env)}[/blue]...")
    
    with auth.get_client() as client:
        # If specific object requested, use the specific endpoint if it's more efficient, 
        # but the current logic fetches all and filters. 
        # Actually /schema returns everything, let's keep it simple for now or check if /schema/{object} is better.
        endpoint = f"/schema/{object_type}" if object_type else "/schema"
        response = client.get(endpoint)
        
        if response.status_code != 200:
            console.print(f"[bold red]Fetch failed for schemas:[/bold red] {response.status_code}")
            raise typer.Exit(1)
            
        data = response.json()
        
        if object_type:
            # Response is a single schema object
            schemas = {object_type: data}
        else:
            # Response is a map of schemas
            schemas = data
        
        if not isinstance(schemas, dict):
            console.print("[bold red]Unexpected response format for schemas.[/bold red]")
            raise typer.Exit(1)

        target_dir = root / "schemas"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        count = 0
        for api_name, schema_data in schemas.items():
            file_path = target_dir / f"{api_name}.json"
            with open(file_path, "w") as f:
                json.dump(schema_data, f, indent=4)
            count += 1
            
        console.print(f"[green]✓[/green] Synchronized {count} schema files to {target_dir}")

@push_app.command(name="metadata")
def push(
    api_name: str = typer.Argument(None, help="Specific object directory to push (e.g., record_trigger)."),
    file_name: str = typer.Argument(None, help="Specific file to push (e.g., trigger_name.py)."),
    manifest: str = typer.Option(None, "--manifest", "-m", help="Path to a deployment manifest JSON file."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Upload local changes to the Valstorm cloud.
    """
    root = get_project_root()
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)

    object_root = root / "object"
    if not object_root.exists():
        console.print("[yellow]No 'object' directory found. Nothing to push.[/yellow]")
        return

    # Identify which types we have locally
    manifest_data = None
    if manifest:
        manifest_path = Path(manifest)
        if not manifest_path.exists():
            console.print(f"[bold red]Manifest file not found:[/bold red] {manifest}")
            raise typer.Exit(1)
        with open(manifest_path, "r") as f:
            manifest_data = json.load(f).get("objects", {})
        types = [t for t in manifest_data.keys() if (object_root / t).exists()]
    elif api_name:
        types = [api_name]
    else:
        types = [d.name for d in object_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
        
        # Filter types by configuration if present
        try:
            with open(root / "valstorm.json", "r") as f:
                config = json.load(f)
                configured_objects = config.get("objects")
                if configured_objects:
                    types = [t for t in types if t in configured_objects]
        except Exception:
            pass
    
    if not types:
        console.print("[yellow]No object types found in 'object' directory.[/yellow]")
        return

    for file_type in types:
        local_dir = object_root / file_type
        
        metadata = []
        # Load legacy monolithic file if present
        legacy_meta = local_dir / f"{file_type}_metadata.json"
        if legacy_meta.exists():
            try:
                with open(legacy_meta, "r") as f:
                    metadata.extend(json.load(f))
            except Exception:
                pass
                
        # Load individual JSON metadata files
        for meta_file in local_dir.glob("*.json"):
            if meta_file.name == f"{file_type}_metadata.json":
                continue
            try:
                with open(meta_file, "r") as f:
                    record_data = json.load(f)
                    if isinstance(record_data, dict):
                        metadata.append(record_data)
            except Exception:
                pass
            
        updates_payload = []
        creates_payload = []
        
        # Map current metadata for easy lookup
        meta_map = {r.get("file_name"): r for r in metadata if r.get("file_name")}
        
        # Scan local directory for changes and new files
        glob_pattern = file_name if file_name else "*.py"
        files_to_scan = []
        if manifest_data and file_type in manifest_data:
            manifest_files = manifest_data[file_type]
            if manifest_files == '*':
                files_to_scan = list(local_dir.glob(glob_pattern))
            elif isinstance(manifest_files, list):
                files_to_scan = [local_dir / f for f in manifest_files if (local_dir / f).exists()]
        else:
            files_to_scan = list(local_dir.glob(glob_pattern))

        for file_path in files_to_scan:
            current_file_name = file_path.name
            with open(file_path, "r") as f:
                local_code = f.read()
            
            if current_file_name in meta_map:
                # This is an existing file, check for updates
                record = meta_map[current_file_name]
                if local_code != record.get("code"):
                    updates_payload.append({
                        "id": record["id"],
                        "code": local_code,
                        "app": record.get("app")
                    })
            else:
                # This is a NEW file, we need to create it in the cloud
                console.print(f"Detected new local {file_type}: [cyan]{current_file_name}[/cyan]")
                if typer.confirm(f"Do you want to create {current_file_name} in the cloud?"):
                    name = typer.prompt(f"Display name for this {file_type}", default=current_file_name.replace(".py", "").replace("_", " ").title())
                    app_id = typer.prompt("App ID (The UUID of the Valstorm App this belongs to)")
                    
                    new_record = {
                        "name": name,
                        "file_name": current_file_name,
                        "code": local_code,
                        "app": app_id,
                        "active": True
                    }
                    
                    if file_type == "record_trigger":
                        new_record["object_api_name"] = typer.prompt("Object API Name (e.g., contact, lead)")
                        new_record["trigger_type"] = typer.prompt("Trigger Type (before_upsert, after_upsert, etc)", default="after_upsert")
                    
                    creates_payload.append(new_record)
        
        # 1. Handle Creates
        if creates_payload:
            console.print(f"Creating {len(creates_payload)} new [cyan]{file_type}[/cyan]s on [blue]{get_api_base_url(auth.env)}[/blue]...")
            with auth.get_client() as client:
                response = client.post(f"/object/{file_type}", json=creates_payload)
                if response.status_code in [200, 201]:
                    console.print(f"[bold green]✓ Successfully created {file_type} records.[/bold green]")
                    newly_created = response.json() if isinstance(response.json(), list) else [response.json()]
                    metadata.extend(newly_created)
                else:
                    console.print(f"[bold red]Create failed for {file_type}:[/bold red] {response.status_code}")
                    console.print(response.text)

        # 2. Handle Updates
        if updates_payload:
            console.print(f"Pushing {len(updates_payload)} updates for [cyan]{file_type}[/cyan] to [blue]{get_api_base_url(auth.env)}[/blue]...")
            with auth.get_client() as client:
                response = client.patch(f"/object/{file_type}", json=updates_payload)
                if response.status_code in [200, 204]:
                    console.print(f"[bold green]✓ Successfully updated {file_type} records.[/bold green]")
                    updated_records = response.json() if response.status_code == 200 else []
                    if updated_records:
                        # Refresh metadata map for updating
                        current_meta_map = {r["id"]: r for r in metadata}
                        for updated in updated_records:
                            current_meta_map[updated["id"]] = updated
                        metadata = list(current_meta_map.values())
                else:
                    console.print(f"[bold red]Push failed for {file_type}:[/bold red] {response.status_code}")
                    console.print(response.text)
        
        # Save updated metadata back to disk
        if creates_payload or updates_payload:
            for record in metadata:
                safe_name = "".join(c for c in str(record.get("name", "unnamed")) if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
                record_id = record.get("id", "noid")
                with open(local_dir / f"{safe_name}_{record_id}.json", "w") as f:
                    json.dump(record, f, indent=4)
        
        if not (creates_payload or updates_payload):
            console.print(f"No changes detected for [cyan]{file_type}[/cyan]s.")

@push_app.command(name="web")
def push_web(
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Override the output base directory for scaffolded web pages."),
    profile: str = typer.Option(None, "--profile", "-p", help="Override the auth profile."),
    env: str = typer.Option(None, "--env", "-e", help="Override the target environment.")
):
    """
    Push local web pages (markdown documents with YAML frontmatter) from the web folder back to the Valstorm cloud.
    """
    root = get_project_root()
    output_base_dir = Path(output_dir) if output_dir else root / "web"
    metadata_path = root / "object" / "app_page" / "app_page_metadata.json"
    
    auth = get_auth(profile=profile, env=env)
    if not auth.ensure_valid_token():
        console.print("[bold red]Authentication failed.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    if not output_base_dir.exists():
        console.print(f"[bold red]Error:[/bold red] Local web folder not found at {output_base_dir}")
        raise typer.Exit(1)
        
    console.print(f"Scanning local web pages in [blue]{output_base_dir}[/blue]...")
    
    try:
        creates_payload, updates_payload, merged_metadata = prepare_web_push(
            root_path=root,
            output_base_dir=output_base_dir
        )
    except ValueError as e:
        console.print(f"[bold red]Error preparing push:[/bold red] {e}")
        raise typer.Exit(1)
        
    if not creates_payload and not updates_payload:
        console.print("[yellow]No local changes or new files detected in the web folder.[/yellow]")
        return
        
    console.print(f"Found [green]{len(creates_payload)} new pages[/green] to create and [cyan]{len(updates_payload)} pages[/cyan] to update.")
    
    if not typer.confirm("Do you want to push these changes to the cloud?"):
        console.print("[yellow]Push cancelled.[/yellow]")
        return
        
    # 1. Handle Creates
    if creates_payload:
        console.print(f"Creating {len(creates_payload)} new pages on [blue]{get_api_base_url(auth.env)}[/blue]...")
        with auth.get_client() as client:
            response = client.post("/object/app_page", json=creates_payload)
            if response.status_code in [200, 201]:
                console.print("[bold green]✓ Successfully created new app pages.[/bold green]")
                newly_created = response.json() if isinstance(response.json(), list) else [response.json()]
                
                created_map = {r["slug"]: r for r in newly_created if r.get("slug")}
                for i, r in enumerate(merged_metadata):
                    if r.get("slug") in created_map:
                        merged_metadata[i] = created_map[r["slug"]]
            else:
                console.print(f"[bold red]Create failed:[/bold red] {response.status_code}")
                console.print(response.text)
                raise typer.Exit(1)
                
    # 2. Handle Updates
    if updates_payload:
        console.print(f"Updating {len(updates_payload)} existing pages on [blue]{get_api_base_url(auth.env)}[/blue]...")
        with auth.get_client() as client:
            response = client.patch("/object/app_page", json=updates_payload)
            if response.status_code in [200, 204]:
                console.print("[bold green]✓ Successfully updated existing app pages.[/bold green]")
                if response.status_code == 200:
                    updated_records = response.json() if isinstance(response.json(), list) else [response.json()]
                    updated_map = {r["id"]: r for r in updated_records if r.get("id")}
                    for i, r in enumerate(merged_metadata):
                        if r.get("id") in updated_map:
                            merged_metadata[i] = updated_map[r["id"]]
            else:
                console.print(f"[bold red]Update failed:[/bold red] {response.status_code}")
                console.print(response.text)
                raise typer.Exit(1)
                
    # Save the updated merged metadata JSON back to disk
    try:
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(merged_metadata, f, indent=4)
        console.print(f"[green]✓ Saved updated local metadata mapping to {metadata_path}[/green]")
    except Exception as e:
        console.print(f"[bold red]Error saving local metadata file:[/bold red] {e}")
        
    console.print("[bold green]✓ Push completed successfully![/bold green]")

