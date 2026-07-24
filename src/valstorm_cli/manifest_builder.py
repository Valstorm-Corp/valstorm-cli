from pathlib import Path
from typing import Set, Dict, Any

def build_manifest_from_files(files: Set[Path], root_dir: Path) -> Dict[str, Any]:
    """
    Scans a set of files and maps them to Valstorm metadata object types
    or database schemas. Builds a valid manifest data structure.
    """
    manifest = {
        "version": "1.0",
        "description": "Git diff generated deployment manifest",
        "objects": {},
        "schemas": []
    }
    
    for file_path in files:
        try:
            rel_path = file_path.relative_to(root_dir)
        except ValueError:
            continue  # The file is not under the workspace root directory
            
        parts = rel_path.parts
        if not parts:
            continue
            
        # 1. Match Schemas (saved under <workspace>/schemas/<schema_name>.json)
        if parts[0] == "schemas" and file_path.suffix == ".json":
            manifest["schemas"].append(file_path.stem)
            
        # 2. Match Object Files (saved under <workspace>/object/<object_type>/<file_name>)
        elif parts[0] == "object" and len(parts) >= 3:
            obj_type = parts[1]
            file_name = parts[2]
            
            # We care about actual files (code, JSON metadata, or template files)
            if file_path.is_file() or file_path.suffix in (".py", ".json", ".yaml", ".yml", ".md", ".html"):
                stem_name = file_path.stem
                
                # Exclude monolithic legacy metadata JSON or any summary/config file
                if file_name == f"{obj_type}_metadata.json":
                    continue
                # Exclude individual companion metadata JSONs from being listed twice in code lists
                # Usually we want function and record_trigger listings to point to the code .py filename,
                # while other object types might point directly to .json metadata filenames.
                if obj_type in ("function", "record_trigger"):
                    target_name = f"{stem_name}.py"
                else:
                    # For other types (e.g. workspace, permission, app, ai_agent), target the specific file name
                    target_name = file_name
                
                # Check for companion metadata JSON filenames that end with `{stem_name}_{id}.json`
                # If it's a companion metadata JSON file for a python file, normalize it to the python file
                if obj_type in ("function", "record_trigger") and file_path.suffix == ".json":
                    # If there's an underscore, it might be {name}_{uuid}.json
                    if "_" in stem_name:
                        parts_of_stem = stem_name.rsplit("_", 1)
                        # If the last segment looks like an ID, use the first segment
                        if len(parts_of_stem) == 2 and any(c.isdigit() for c in parts_of_stem[1]):
                            target_name = f"{parts_of_stem[0]}.py"
                        else:
                            target_name = f"{stem_name}.py"
                    else:
                        target_name = f"{stem_name}.py"
                        
                if obj_type not in manifest["objects"]:
                    manifest["objects"][obj_type] = []
                    
                if target_name not in manifest["objects"][obj_type]:
                    manifest["objects"][obj_type].append(target_name)
                    
    # Clean up empty properties
    if not manifest["schemas"]:
        manifest.pop("schemas")
    if not manifest["objects"]:
        manifest["objects"] = {}
        
    return manifest
