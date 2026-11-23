import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from valstorm import ValstormClient, ValstormError

from .auth import requires_auth
from .bundler import bundle_local_app

console = Console()
app_cmds = typer.Typer(help="Manage Valstorm applications (list, install, package, deploy, promote, publish).")


@app_cmds.command("list")
@requires_auth
def list_apps(
    marketplace: bool = typer.Option(False, "--marketplace", "-m", help="List available marketplace apps instead of installed apps."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    List installed apps (or marketplace catalog with `--marketplace`).
    """
    try:
        apps = sdk.apps.list_marketplace() if marketplace else sdk.apps.list_installed()
    except ValstormError as e:
        console.print(f"[bold red]Failed to list apps:[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(apps, indent=2))
        return

    if not apps:
        console.print("[yellow]No apps found.[/yellow]")
        return

    title = "Marketplace Applications" if marketplace else "Installed Applications"
    table = Table(title=title)
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Description")

    for item in apps:
        if isinstance(item, dict):
            table.add_row(
                str(item.get("id", "")),
                str(item.get("name", "")),
                str(item.get("version", "") or "-"),
                str(item.get("description", "") or "")[:80],
            )
    console.print(table)


@app_cmds.command("envs")
@requires_auth
def list_environments(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    List promotion target environments (production + sandboxes) in the organization.
    """
    try:
        envs = sdk.apps.list_environments()
    except ValstormError as e:
        console.print(f"[bold red]Failed to list environments:[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(envs, indent=2))
        return

    if not envs:
        console.print("[yellow]No environments found.[/yellow]")
        return

    table = Table(title="Promotion Environments")
    table.add_column("Org ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Type", style="magenta")

    for e_item in envs:
        if isinstance(e_item, dict):
            table.add_row(
                str(e_item.get("id") or e_item.get("org_id") or ""),
                str(e_item.get("name") or ""),
                str(e_item.get("type") or ("sandbox" if e_item.get("is_sandbox") else "production")),
            )
    console.print(table)


@app_cmds.command("install")
@requires_auth
def install_app(
    app_id: str = typer.Argument(..., help="Marketplace app ID to install."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Install an application from the marketplace into the current organization.
    """
    try:
        res = sdk.apps.install(app_id)
    except ValstormError as e:
        console.print(f"[bold red]Failed to install app '{app_id}':[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(res, indent=2))
        return
    console.print(f"[bold green]✓ Successfully installed app '{app_id}'.[/bold green]")


@app_cmds.command("uninstall")
@requires_auth
def uninstall_app(
    app_id: str = typer.Argument(..., help="Installed app ID to uninstall."),
    delete_records: bool = typer.Option(False, "--delete-records", help="Also delete records owned by this app."),
    force: bool = typer.Option(False, "--force", "-y", help="Skip confirmation prompt."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Uninstall an application from the current organization.
    """
    if not force:
        extra = " and DELETE its records" if delete_records else ""
        if not typer.confirm(f"Are you sure you want to uninstall app '{app_id}'{extra}?"):
            console.print("Operation cancelled.")
            raise typer.Exit(0)

    try:
        res = sdk.apps.uninstall(app_id, delete_records=delete_records)
    except ValstormError as e:
        console.print(f"[bold red]Failed to uninstall app '{app_id}':[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(res, indent=2))
        return
    console.print(f"[bold green]✓ Successfully uninstalled app '{app_id}'.[/bold green]")


@app_cmds.command("package")
@requires_auth
def package_app(
    app_id: str = typer.Argument(..., help="App ID to snapshot/package into a portable bundle."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write packaged bundle JSON to a file."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Package an application into a portable JSON bundle.
    """
    try:
        bundle = sdk.apps.package(app_id)
    except ValstormError as e:
        console.print(f"[bold red]Failed to package app '{app_id}':[/bold red] {e}")
        raise typer.Exit(1)

    if output:
        output.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        console.print(f"[bold green]✓ Saved packaged bundle to {output}[/bold green]")
    else:
        print(json.dumps(bundle, indent=2))


@app_cmds.command("deploy")
@requires_auth
def deploy_local_app(
    app_dir: Path = typer.Argument(Path("."), help="Path to local app directory containing valstorm.json."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Compile and print the bundle without deploying."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Bundle a local Valstorm app directory and deploy it via `PUT /v1/apps/deploy`.
    """
    try:
        bundle = bundle_local_app(app_dir.resolve())
    except FileNotFoundError as e:
        console.print(f"[bold red]Bundling Error:[/bold red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected error during bundling:[/bold red] {e}")
        raise typer.Exit(1)

    app_name = bundle.get("name", app_dir.name)
    schema_count = len(bundle.get("schemas", []))
    record_count = sum(len(v) for v in bundle.get("records", {}).values())
    console.print(f"Bundled [bold cyan]{app_name}[/bold cyan]: {schema_count} schemas, {record_count} records.")

    if dry_run:
        print(json.dumps(bundle, indent=2))
        return

    try:
        res = sdk.apps.deploy(bundle)
    except ValstormError as e:
        console.print(f"[bold red]Deployment failed:[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(res, indent=2))
        return
    console.print(f"[bold green]✓ Successfully deployed '{app_name}'![/bold green]")


@app_cmds.command("promote")
@requires_auth
def promote_app(
    app_id: str = typer.Argument(..., help="App ID to promote."),
    to: str = typer.Option(..., "--to", "-t", help="Target organization or sandbox org ID (see `valstorm app envs`)."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Promote an application bundle from the current environment to a target sandbox or parent org.
    """
    try:
        res = sdk.apps.promote(app_id, target_org_id=to)
    except ValstormError as e:
        console.print(f"[bold red]Promotion failed:[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(res, indent=2))
        return
    console.print(f"[bold green]✓ Successfully promoted app '{app_id}' to '{to}'![/bold green]")


@app_cmds.command("publish")
@requires_auth
def publish_app(
    app_id: str = typer.Argument(..., help="App ID to publish to the marketplace."),
    update_subscribers: bool = typer.Option(
        False,
        "--update-subscribers",
        help="Also roll out the published update to all subscribing organizations.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Publish an application to the marketplace (and optionally update subscribers).
    """
    try:
        pub_res = sdk.apps.deploy_to_marketplace(app_id)
        sub_res = None
        if update_subscribers:
            sub_res = sdk.apps.update_subscribers(app_id)
    except ValstormError as e:
        console.print(f"[bold red]Publish failed:[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        out = {"publish": pub_res}
        if sub_res is not None:
            out["subscribers"] = sub_res
        print(json.dumps(out, indent=2))
        return

    console.print(f"[bold green]✓ Published app '{app_id}' to marketplace.[/bold green]")
    if sub_res is not None:
        console.print("[bold green]✓ Updated subscribing organizations.[/bold green]")
