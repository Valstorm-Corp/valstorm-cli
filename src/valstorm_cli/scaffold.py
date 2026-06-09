import os
import json
import uuid
from pathlib import Path

def extract_rich_text_values(node):
    """
    Recursively searches the node tree to find all RichText values in order.
    """
    if not isinstance(node, dict):
        return []
    
    values = []
    props = node.get("props", {})
    if isinstance(props, dict):
        if props.get("component_type") == "RichText" and "value" in props:
            val = props["value"]
            if val:
                values.append(val)
                
    # Recurse children
    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            values.extend(extract_rich_text_values(child))
            
    return values

def format_frontmatter(metadata):
    """
    Formats metadata dictionary as YAML frontmatter.
    """
    lines = ["---"]
    for k, v in metadata.items():
        if v is not None:
            # Safely encode values as JSON string for YAML compatibility
            val_str = json.dumps(v, ensure_ascii=False)
            lines.append(f"{k}: {val_str}")
    lines.append("---")
    return "\n".join(lines)

def parse_frontmatter(content):
    """
    Parses simple YAML frontmatter.
    Returns: (metadata_dict, body_text)
    """
    if not content.startswith("---"):
        return {}, content
    
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
        
    yaml_text = parts[1]
    body_text = parts[2].strip()
    
    metadata = {}
    for line in yaml_text.strip().splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        try:
            # Try to load as JSON to decode quotes/escapes
            metadata[k] = json.loads(v)
        except Exception:
            # Fallback to string stripping
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            metadata[k] = v
    return metadata, body_text

def _update_rich_text_in_tree(node, new_value):
    """
    Recursively searches the tree to find and update the first RichText component's value.
    Returns True if updated, False otherwise.
    """
    if not isinstance(node, dict):
        return False
    
    props = node.setdefault("props", {})
    if props.get("component_type") == "RichText":
        props["value"] = new_value
        return True
        
    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            if _update_rich_text_in_tree(child, new_value):
                return True
    return False

def _add_rich_text_to_tree(data_list, new_value):
    """
    Adds a new RichText component to the main dropzone of the data list.
    """
    new_id = str(uuid.uuid4())
    rich_text_node = {
        "id": new_id,
        "children": [],
        "edges": [],
        "parent": "main-dropzone",
        "props": {
            "api_name": "rich_text",
            "value": new_value,
            "class_name": "",
            "category": "HTML",
            "component_type": "RichText",
            "schema_name": "rich_text"
        }
    }
    
    # Find dropzone with id "main-dropzone" or first dropzone
    for node in data_list:
        if isinstance(node, dict):
            props = node.get("props", {})
            if props.get("id") == "main-dropzone" or props.get("component_type") == "DropZone":
                node.setdefault("children", []).append(rich_text_node)
                return True
                
    # Fallback: create dropzone and append rich text
    main_dropzone = {
        "id": 1,
        "children": [rich_text_node],
        "edges": [],
        "parent": None,
        "props": {
            "api_name": "dropzone",
            "class_name": "min-h-[100px] flex flex-col p-1 gap-4",
            "category": "Drag & Drop",
            "component_type": "DropZone",
            "schema_name": "dropzone",
            "paper": False,
            "children": [],
            "id": "main-dropzone",
            "name": "Main Dropzone"
        }
    }
    data_list.append(main_dropzone)
    return True

def run_web_scaffolding(root_path: Path, output_base_dir: Path, progress_callback=None):
    """
    Core scaffolding service logic.
    Calls progress_callback for each scaffolded or skipped file.
    Returns: (total_records, scaffolded_count, skipped_count, tag_counts)
    """
    metadata_path = root_path / "object" / "app_page" / "app_page_metadata.json"
    
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found at {metadata_path}")
        
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
    except Exception as e:
        raise ValueError(f"Error parsing JSON from {metadata_path}: {e}")
        
    scaffolded_count = 0
    skipped_count = 0
    tag_counts = {}
    
    for record in records:
        rec_type = record.get("type")
        rec_tag = record.get("tag")
        
        # Filter for type == "Web Page" and tag in ["Docs", "Marketing"] (case-insensitive)
        if rec_type != "Web Page":
            continue
            
        if not rec_tag or not isinstance(rec_tag, str) or rec_tag.lower() not in ["docs", "marketing"]:
            continue
            
        slug = record.get("slug")
        if not slug:
            if progress_callback:
                progress_callback("skip", record=record, tag=rec_tag)
            skipped_count += 1
            continue
            
        slug = slug.strip("/")
        
        # Extract rich text content
        content_values = []
        data = record.get("data", [])
        if isinstance(data, list):
            for root_node in data:
                content_values.extend(extract_rich_text_values(root_node))
                
        markdown_body = "\n\n".join(content_values) if content_values else ""
        
        # Build metadata for frontmatter
        metadata = {
            "id": record.get("id"),
            "name": record.get("name"),
            "created_date": record.get("created_date"),
            "modified_date": record.get("modified_date"),
            "slug": record.get("slug"),
            "tag": record.get("tag"),
            "seo_title": record.get("seo_title"),
            "seo_description": record.get("seo_description"),
            "seo_keywords": record.get("seo_keywords"),
            "canonical_url": record.get("canonical_url"),
        }
        
        frontmatter = format_frontmatter(metadata)
        
        # Combine frontmatter and markdown body
        file_content = frontmatter
        if markdown_body:
            file_content += f"\n\n{markdown_body}\n"
        else:
            file_content += "\n"
            
        # Target file resolution
        tag_folder = rec_tag.strip() if rec_tag else "Uncategorized"
        target_file_path = output_base_dir / tag_folder / f"{slug}.md"
        parent_dir = target_file_path.parent
        
        parent_dir.mkdir(parents=True, exist_ok=True)
        with open(target_file_path, "w", encoding="utf-8") as out_f:
            out_f.write(file_content)
            
        scaffolded_count += 1
        tag_counts[rec_tag] = tag_counts.get(rec_tag, 0) + 1
        
        if progress_callback:
            progress_callback("scaffold", record=record, tag=rec_tag, tag_folder=tag_folder, slug=slug)
            
    return len(records), scaffolded_count, skipped_count, tag_counts

def prepare_web_push(root_path: Path, output_base_dir: Path):
    """
    Scans output_base_dir for .md files, parses them, and compares with
    object/app_page/app_page_metadata.json.
    Returns: (creates_payload, updates_payload, merged_metadata)
    """
    metadata_path = root_path / "object" / "app_page" / "app_page_metadata.json"
    
    # Load current local metadata state (or empty list if it doesn't exist)
    records = []
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except Exception:
            records = []
            
    # Index records by ID
    records_by_id = {r["id"]: r for r in records if r.get("id")}
    
    creates_payload = []
    updates_payload = []
    
    # Recursively find all .md files in output_base_dir
    md_files = list(output_base_dir.rglob("*.md"))
    
    processed_ids = set()
    
    for file_path in md_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            raise ValueError(f"Error reading local file {file_path}: {e}")
            
        metadata, markdown_body = parse_frontmatter(file_content)
        
        # Determine tag from parent directory if not explicitly in frontmatter
        try:
            rel_parts = file_path.parent.relative_to(output_base_dir).parts
            dir_tag = rel_parts[0] if rel_parts else None
        except Exception:
            dir_tag = None
            
        file_tag = metadata.get("tag") or dir_tag or "Docs"
        
        # Determine slug
        try:
            # Reconstruct slug from relative path to the tag folder
            rel_to_tag = file_path.relative_to(output_base_dir / file_tag)
            # Remove extension
            file_slug = str(rel_to_tag.with_suffix(""))
        except Exception:
            file_slug = metadata.get("slug") or file_path.stem
            
        rec_id = metadata.get("id")
        
        if rec_id and rec_id in records_by_id:
            # We are updating an existing page!
            existing_record = records_by_id[rec_id]
            
            # Update root fields
            existing_record["name"] = metadata.get("name") or existing_record.get("name") or file_path.stem.replace("-", " ").title()
            existing_record["slug"] = file_slug
            existing_record["tag"] = file_tag
            existing_record["seo_title"] = metadata.get("seo_title") or existing_record.get("seo_title")
            existing_record["seo_description"] = metadata.get("seo_description") or existing_record.get("seo_description")
            existing_record["seo_keywords"] = metadata.get("seo_keywords") or existing_record.get("seo_keywords")
            existing_record["canonical_url"] = metadata.get("canonical_url") or existing_record.get("canonical_url")
            existing_record["author_override"] = metadata.get("author_override") or existing_record.get("author_override")
            
            # Ensure data list exists
            data_list = existing_record.get("data", [])
            if not isinstance(data_list, list):
                data_list = []
                existing_record["data"] = data_list
                
            # Update RichText component
            updated_rich_text = False
            for root_node in data_list:
                if _update_rich_text_in_tree(root_node, markdown_body):
                    updated_rich_text = True
                    break
                    
            if not updated_rich_text:
                _add_rich_text_to_tree(data_list, markdown_body)
                
            updates_payload.append(existing_record)
            processed_ids.add(rec_id)
        else:
            # We are creating a brand new page!
            new_id = rec_id or str(uuid.uuid4())
            
            new_record = {
                "id": new_id,
                "name": metadata.get("name") or file_path.stem.replace("-", " ").title(),
                "created_date": None,
                "modified_date": None,
                "created_by": None,
                "modified_by": None,
                "type": "Web Page",
                "description": None,
                "object": None,
                "data": [],
                "slug": file_slug,
                "tag": file_tag,
                "remove_record_page_save_button": False,
                "base_route": "docs" if file_tag.lower() == "docs" else None,
                "icon": None,
                "author_override": metadata.get("author_override"),
                "canonical_url": metadata.get("canonical_url"),
                "seo_description": metadata.get("seo_description"),
                "seo_image": None,
                "seo_keywords": metadata.get("seo_keywords"),
                "seo_title": metadata.get("seo_title"),
                "shared_with": []
            }
            
            _add_rich_text_to_tree(new_record["data"], markdown_body)
            creates_payload.append(new_record)
            processed_ids.add(new_id)
            
    # Combine processed existing records and newly created ones for the final saved local metadata
    merged_metadata = []
    
    # Add all files that were successfully parsed/scaffolded (existing + new)
    for record in updates_payload:
        merged_metadata.append(record)
    for record in creates_payload:
        merged_metadata.append(record)
        
    # Preserve other existing records (e.g. record pages, workspaces)
    for record in records:
        rid = record.get("id")
        if rid and rid not in processed_ids:
            merged_metadata.append(record)
            
    return creates_payload, updates_payload, merged_metadata
