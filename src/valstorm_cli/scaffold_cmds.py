import typer
import json
from typing import Optional
from pathlib import Path
from rich.console import Console
from .scaffold import run_web_scaffolding
from .auth import get_auth, get_project_root

console = Console()
scaffold_app = typer.Typer(help="Generate local files from Valstorm records.")





@scaffold_app.command(name="web")
def scaffold_web(
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Override the output base directory for scaffolded web pages.")
):
    """
    Scaffold app pages (tagged Docs/Marketing) of type 'Web Page' into organized local Markdown files.
    """
    root = get_project_root()
    output_base_dir = Path(output_dir) if output_dir else root / "web"
    
    def progress_callback(event, **kwargs):
        if event == "scaffold":
            rec_tag = kwargs.get("tag")
            record = kwargs.get("record")
            tag_folder = kwargs.get("tag_folder")
            slug = kwargs.get("slug")
            console.print(f"Scaffolded: \\\\[[cyan]{rec_tag}[/cyan]] '{record.get('name')}' -> [green]{tag_folder}/{slug}.md[/green]")
        elif event == "skip":
            rec_tag = kwargs.get("tag")
            record = kwargs.get("record")
            console.print(f"[yellow]Warning:[/yellow] Page '{record.get('name')}' (ID: {record.get('id')}) has tag '{rec_tag}' but no slug. Skipping.")

    try:
        total_records, scaffolded_count, skipped_count, tag_counts = run_web_scaffolding(
            root_path=root,
            output_base_dir=output_base_dir,
            progress_callback=progress_callback
        )
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("[yellow]Hint: Run 'valstorm pull' first to sync metadata records from the cloud.[/yellow]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)
        
    console.print("\n" + "="*50)
    console.print("[bold green]SCAFFOLDING COMPLETED SUCCESSFULLY![/bold green]")
    console.print("="*50)
    console.print(f"Total Pages Processed: {scaffolded_count}")
    for t, count in tag_counts.items():
        console.print(f"  - {t}: {count} pages")
    if skipped_count > 0:
        console.print(f"Pages Skipped: {skipped_count}")
    console.print(f"All markdown files written to: [blue]{output_base_dir}[/blue]")
    console.print("="*50)

@scaffold_app.command(name="docs")
def scaffold_docs(
    profile: str = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: str = typer.Option(None, "--env", "-e", help="Target environment.")
):
    """
    Fetch documentation records and scaffold them as Markdown files.
    """
    auth = get_auth(profile=profile, env=env)
    
    if not auth.ensure_valid_token():
        console.print("[bold red]Not logged in or token expired.[/bold red] Please run `valstorm login`.")
        raise typer.Exit(1)
        
    try:
        root = get_project_root()
    except Exception:
        root = Path.cwd()
        
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    with auth.get_client() as client:
        try:
            response = client.post("/query", json={
                "query": "SELECT * FROM documentation"
            })
            
            if response.status_code != 200:
                console.print(f"[bold red]Query failed ({response.status_code}):[/bold red] {response.text}")
                raise typer.Exit(1)
                
            data = response.json()
            
            if not isinstance(data, list):
                console.print("[yellow]Expected a list of documentation records.[/yellow]")
                raise typer.Exit(1)
                
            console.print(f"Found {len(data)} documentation records. Scaffolding...")
            
            def tree_to_markdown(node):
                if not node:
                    return ""
                    
                if isinstance(node, list):
                    return "\n".join(tree_to_markdown(child) for child in node if child)
                
                md = ""
                component = node.get("component", "")
                props = node.get("props", {})
                if not component and "component_type" in props:
                    component = props["component_type"]
                    
                children = node.get("children", [])
                
                if component == "Typography":
                    variant = props.get("variant", "body1")
                    text = props.get("text", "")
                    
                    if variant == "h1":
                        md += f"# {text}\n\n"
                    elif variant == "h2":
                        md += f"## {text}\n\n"
                    elif variant == "h3":
                        md += f"### {text}\n\n"
                    elif variant == "h4":
                        md += f"#### {text}\n\n"
                    elif variant == "h5":
                        md += f"##### {text}\n\n"
                    elif variant == "h6":
                        md += f"###### {text}\n\n"
                    else:
                        md += f"{text}\n\n"
                elif component == "Text":
                    md += f"{props.get('text', '')}\n\n"
                elif component == "Paragraph":
                    md += f"{props.get('text', '')}\n\n"
                elif component == "RichText":
                    md += f"{props.get('value', '')}\n\n"
                
                for child in children:
                    child_md = tree_to_markdown(child)
                    if child_md:
                        md += child_md
                    
                return md

            for record in data:
                name = record.get("name", "untitled")
                slug = record.get("slug", "") or name
                category = record.get("category", "uncategorized")
                if not category:
                    category = "uncategorized"
                seo_title = record.get("seo_title", "")
                seo_description = record.get("seo_description", "")
                is_published = record.get("is_published", False)
                
                def sanitize(s):
                    import re
                    s = str(s).lower()
                    s = re.sub(r'[^a-z0-9]+', '-', s)
                    return s.strip('-')
                
                safe_category = sanitize(category)
                if not safe_category:
                    safe_category = "uncategorized"
                    
                safe_slug = sanitize(slug)
                if not safe_slug:
                    continue
                    
                cat_dir = docs_dir / safe_category
                cat_dir.mkdir(parents=True, exist_ok=True)
                
                file_path = cat_dir / f"{safe_slug}.md"
                
                frontmatter = "---\n"
                frontmatter += f"title: \"{name}\"\n"
                if seo_title:
                    frontmatter += f"seo_title: \"{seo_title}\"\n"
                if seo_description:
                    frontmatter += f"seo_description: \"{seo_description}\"\n"
                frontmatter += f"category: \"{category}\"\n"
                frontmatter += f"is_published: {str(is_published).lower()}\n"
                frontmatter += "---\n\n"
                
                content_json = record.get("content")
                md_body = ""
                
                if content_json:
                    if isinstance(content_json, str):
                        try:
                            content_data = json.loads(content_json)
                        except json.JSONDecodeError:
                            content_data = []
                    else:
                        content_data = content_json
                        
                    md_body = tree_to_markdown(content_data)
                    
                with open(file_path, "w") as f:
                    f.write(frontmatter + md_body)
                    
                console.print(f"[green]✓[/green] Created {file_path.relative_to(root)}")
                
        except httpx.RequestError as e:
            console.print(f"[bold red]Connection Error:[/bold red] {e}")
            raise typer.Exit(1)

if __name__ == "__main__":
    app()




