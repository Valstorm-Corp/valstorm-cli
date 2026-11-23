import json
from pathlib import Path
from typing import Any, Dict

from .sync import KNOWN_METADATA_OBJECTS, STANDARD_OBJECTS


def bundle_local_app(app_dir: Path) -> Dict[str, Any]:
    """
    Compiles a local Open Valstorm workspace directory into an AppBundle dictionary
    ready for `PUT /v1/apps/deploy`.

    Reads:
      - `<app_dir>/valstorm.json`
      - `<app_dir>/schemas/*.json`
      - `<app_dir>/<api_name>/*.py` and `<app_dir>/<api_name>/*.json`
      - `<app_dir>/.valstorm/metadata.json` (for tracked IDs & metadata)
    """
    root = app_dir.resolve()
    config_path = root / "valstorm.json"
    if not config_path.exists():
        raise FileNotFoundError(f"valstorm.json not found in {root}")

    config = json.loads(config_path.read_text(encoding="utf-8"))

    local_meta: Dict[str, Any] = {}
    meta_file = root / ".valstorm" / "metadata.json"
    if meta_file.exists():
        try:
            loaded = json.loads(meta_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                local_meta = loaded
        except Exception:
            pass

    bundle: Dict[str, Any] = {
        "name": config.get("name", root.name),
        "description": config.get("description", ""),
        "version": config.get("version", "1.0.0"),
        "schemas": [],
        "records": {},
    }
    if config.get("app_id"):
        bundle["id"] = config["app_id"]
    elif config.get("id"):
        bundle["id"] = config["id"]

    # 1. Bundle schemas
    schemas_dir = root / "schemas"
    if schemas_dir.exists():
        for sf in sorted(schemas_dir.glob("*.json")):
            schema_doc = json.loads(sf.read_text(encoding="utf-8"))
            if isinstance(schema_doc, dict):
                schema_doc.setdefault("api_name", sf.stem)
                bundle["schemas"].append(schema_doc)

    # 2. Bundle object directories using exact api_name folders
    configured_objs = config.get("objects")
    allowed_folders = KNOWN_METADATA_OBJECTS | set(STANDARD_OBJECTS)
    if isinstance(configured_objs, list):
        allowed_folders |= {str(o).strip() for o in configured_objs if str(o).strip()}

    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name.startswith(".") or folder.name not in allowed_folders:
            continue
        obj_type = folder.name
        type_records: list[dict[str, Any]] = []

        for f in sorted(folder.rglob("*")):
            if not f.is_file() or f.suffix not in (".py", ".json"):
                continue
            rel_key = str(f.relative_to(root))
            tracked = local_meta.get(rel_key, {})

            if f.suffix == ".py":
                rec = dict(tracked)
                rec.pop("type", None)
                rec["code"] = f.read_text(encoding="utf-8")
                rec.setdefault("file_name", f.name)
                rec.setdefault("name", f.stem)
                type_records.append(rec)
            else:
                rec = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(rec, dict):
                    if tracked.get("id") and not rec.get("id"):
                        rec["id"] = tracked["id"]
                    rec.setdefault("file_name", f.name)
                    type_records.append(rec)

        if type_records:
            bundle["records"][obj_type] = type_records

    return bundle
