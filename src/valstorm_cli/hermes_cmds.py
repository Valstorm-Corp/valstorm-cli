import typer
import subprocess
import shutil
import os
from pathlib import Path
from rich.console import Console

hermes_app = typer.Typer(help="Manage distributed Hermes Agentic Networks", no_args_is_help=True)
console = Console()

HERMES_HOME = Path.home() / ".hermes"
NETWORK_DIR = HERMES_HOME / ".valstorm-network"
PROFILES_DIR = HERMES_HOME / "profiles"

def ensure_git():
    if not shutil.which("git"):
        console.print("[bold red]Error:[/bold red] Git is required but not installed.")
        raise typer.Exit(1)

def link_profiles():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in NETWORK_DIR.iterdir():
        if item.is_dir() and item.name != ".git":
            target = PROFILES_DIR / item.name
            
            if target.exists() or target.is_symlink():
                console.print(f"  [yellow]Skipping {item.name}:[/yellow] Already exists in profiles.")
            else:
                os.symlink(item, target)
                console.print(f"  [green]Linked {item.name}[/green]")
            
            # Generate default config.yaml if an example exists
            config_example = item / "config.example.yaml"
            config = item / "config.yaml"
            if config_example.exists() and not config.exists():
                shutil.copy2(config_example, config)
                console.print(f"  [dim]Generated default config.yaml for {item.name}[/dim]")

@hermes_app.command("install")
def install(
    repo_url: str = typer.Argument(..., help="The Git repository URL containing the agentic network")
):
    """Onboard a team's agentic network."""
    ensure_git()
    if NETWORK_DIR.exists():
        console.print("[yellow]Network directory already exists. Use 'valstorm hermes sync' to update it.[/yellow]")
        raise typer.Exit(1)
    
    console.print(f"Cloning {repo_url} into {NETWORK_DIR}...")
    res = subprocess.run(["git", "clone", repo_url, str(NETWORK_DIR)], capture_output=True, text=True)
    if res.returncode != 0:
        console.print(f"[bold red]Git clone failed:[/bold red]\n{res.stderr}")
        raise typer.Exit(1)
        
    console.print("Linking profiles...")
    link_profiles()
    console.print("\n[bold green]Network installed successfully![/bold green]")
    console.print("Run `hermes --profile <profile_name>` to begin.")


@hermes_app.command("sync")
def sync():
    """Keep the team's agentic network up to date."""
    ensure_git()
    if not NETWORK_DIR.exists():
        console.print("[bold red]Network not installed. Run 'valstorm hermes install <repo-url>' first.[/bold red]")
        raise typer.Exit(1)
        
    console.print("Pulling latest updates...")
    res = subprocess.run(["git", "-C", str(NETWORK_DIR), "pull"], capture_output=True, text=True)
    if res.returncode != 0:
        console.print(f"[bold red]Git pull failed:[/bold red]\n{res.stderr}")
        raise typer.Exit(1)
        
    console.print(res.stdout.strip())
    console.print("Updating profile links...")
    link_profiles()
    console.print("\n[bold green]Network synced successfully![/bold green]")
