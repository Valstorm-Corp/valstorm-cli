from pathlib import Path
from typing import Any, Dict, Set

_IGNORED_TOP_DIRS = {"schemas", "queries", ".valstorm", ".git", "__pycache__"}


def build_manifest_from_files(changed_files: Set[Path], project_root: Path) -> Dict[str, Any]:
    """
    Converts a set of changed workspace file paths into a Valstorm deployment manifest:
      {
        "schemas": ["contact", ...],
        "objects": {
          "function": ["my_fn.py"],
          "record_trigger": ["on_save.py"],
          "schedule_trigger_setting": ["nightly.json"],
          "permission": ["admin.json"],
          "role": ["editor.json"],
          "app": ["crm.json"]
        }
      }
    """
    manifest: Dict[str, Any] = {
        "schemas": [],
        "objects": {},
    }

    root_resolved = project_root.resolve()
    schemas_seen: set[str] = set()
    objects_seen: dict[str, set[str]] = {}

    for file_path in sorted(changed_files):
        try:
            rel = file_path.resolve().relative_to(root_resolved)
        except ValueError:
            continue

        parts = rel.parts
        if len(parts) < 2:
            continue

        top_dir = parts[0]
        if top_dir.startswith("."):
            continue

        # 1. schemas/<api_name>.json
        if top_dir == "schemas" and file_path.suffix == ".json":
            schemas_seen.add(file_path.stem)
            continue

        if top_dir in _IGNORED_TOP_DIRS:
            continue

        # 2. <api_name>/<file_name>
        if file_path.suffix in (".py", ".json"):
            objects_seen.setdefault(top_dir, set()).add(file_path.name)

    if schemas_seen:
        manifest["schemas"] = sorted(schemas_seen)
    else:
        manifest.pop("schemas")

    manifest["objects"] = {k: sorted(v) for k, v in sorted(objects_seen.items())}
    return manifest
