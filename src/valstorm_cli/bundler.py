import json
from pathlib import Path
from typing import Dict, Any, List

def bundle_local_app(app_config_path: Path, workspace_root: Path) -> Dict[str, Any]:
    """
    Reads an app.json config, compiles all associated schemas, and auto-discovers/collects
    all local object metadata records and python source files belonging to the app.
    """
    with open(app_config_path, "r") as f:
        app_config = json.load(f)
        
    app_id = app_config.get("id")
    if not app_id:
        raise ValueError("The 'id' (UUID) of the app is required in the configuration.")
        
    bundle = {
        "id": app_id,
        "name": app_config.get("name", "Unnamed App"),
        "description": app_config.get("description", ""),
        "schemas": [],
        "records": {}
    }
    
    # 1. Resolve and Bundle Schemas
    schemas_dir = workspace_root / "schemas"
    schemas_to_bundle: List[str] = app_config.get("schemas", [])
    
    # Auto-discover schemas if schemas_dir exists
    if schemas_dir.exists():
        for schema_file in schemas_dir.glob("*.json"):
            try:
                with open(schema_file, "r") as sf:
                    schema_data = json.load(sf)
                # If schema belongs to this app or is listed explicitly
                if schema_data.get("app") == app_id or schema_file.stem in schemas_to_bundle:
                    bundle["schemas"].append(schema_data)
            except Exception:
                pass
                
    # 2. Resolve and Bundle Records (functions, record_triggers, workspaces, etc.)
    object_root = workspace_root / "object"
    if object_root.exists():
        for type_dir in object_root.iterdir():
            if not type_dir.is_dir() or type_dir.name.startswith("."):
                continue
                
            file_type = type_dir.name
            type_records = []
            
            # Map of python files to their metadata JSON definitions
            code_files = list(type_dir.glob("*.py"))
            metadata_files = list(type_dir.glob("*.json"))
            
            # Exclude monolith metadata if present
            metadata_files = [m for m in metadata_files if m.name != f"{file_type}_metadata.json"]
            
            # Read metadata JSONs to identify records belonging to this app
            for meta_file in metadata_files:
                try:
                    with open(meta_file, "r") as mf:
                        meta_data = json.load(mf)
                    
                    # Verify if this record belongs to our target app
                    is_app_member = meta_data.get("app") == app_id
                    
                    # Also check if listed in explicit records of config (if provided)
                    explicit_records = app_config.get("records", {}).get(file_type, [])
                    is_explicit = meta_data.get("file_name") in explicit_records or meta_file.name in explicit_records
                    
                    if is_app_member or is_explicit:
                        # If there is a matching code file, read the code on-disk to make sure we push current code
                        file_name = meta_data.get("file_name")
                        if file_name:
                            code_file_path = type_dir / file_name
                            if code_file_path.exists():
                                with open(code_file_path, "r") as cf:
                                    meta_data["code"] = cf.read()
                                    
                        type_records.append(meta_data)
                except Exception:
                    pass
                    
            # If explicit listings were specified but didn't have metadata JSON files,
            # we can create skeleton records for them
            explicit_records = app_config.get("records", {}).get(file_type, [])
            for explicit_file in explicit_records:
                # Check if already added
                if any(r.get("file_name") == explicit_file for r in type_records):
                    continue
                    
                file_path = type_dir / explicit_file
                if file_path.exists():
                    try:
                        with open(file_path, "r") as f_code:
                            code_content = f_code.read()
                        
                        # Generate basic skeleton
                        skeleton = {
                            "name": file_path.stem.replace("_", " ").title(),
                            "file_name": explicit_file,
                            "code": code_content,
                            "app": app_id,
                            "active": True
                        }
                        
                        # Set default trigger fields if applicable
                        if file_type == "record_trigger":
                            skeleton["object_api_name"] = "contact" # default fallback
                            skeleton["trigger_type"] = "after_upsert"
                            
                        type_records.append(skeleton)
                    except Exception:
                        pass
                        
            if type_records:
                bundle["records"][file_type] = type_records
                
    return bundle
