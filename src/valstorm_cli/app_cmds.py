import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from valstorm import ValstormClient, ValstormError

from .auth import requires_auth
from .bundler import bundle_local_app
from .deployment_ui import follow_deployment, render_deployment_report

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
    no_wait: bool = typer.Option(
        False,
        "--no-wait",
        help="Return immediately after queueing the subscriber rollout without waiting for completion.",
    ),
    concurrency: int = typer.Option(
        12,
        "--concurrency",
        min=1,
        max=30,
        help="Bounded concurrent tenant deployments executed by Go open-worker.",
    ),
    include_sandboxes: bool = typer.Option(
        True,
        "--include-sandboxes/--no-sandboxes",
        help="Include subscribed sandbox organizations in the rollout.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """
    Publish an application to the marketplace (and optionally roll out to subscribers with live progress).
    """
    try:
        pub_res = sdk.apps.deploy_to_marketplace(app_id)
        sub_res = None
        if update_subscribers:
            sub_res = sdk.apps.update_subscribers(
                app_id,
                concurrency=concurrency,
                include_sandboxes=include_sandboxes,
                trigger_source="cli",
            )
    except ValstormError as e:
        console.print(f"[bold red]Publish failed:[/bold red] {e}")
        raise typer.Exit(1)

    if not json_output:
        schemas_pub = pub_res.get("schemas_published")
        recs_pub = pub_res.get("records_published")
        counts_note = f" ({schemas_pub} schemas, {recs_pub} records)" if schemas_pub is not None else ""
        console.print(f"[bold green]✓ Published app '{app_id}' to marketplace{counts_note}.[/bold green]")

    if sub_res is None:
        if json_output:
            print(json.dumps({"publish": pub_res}, indent=2))
        return

    job_id = sub_res.get("deployment_job_id") or sub_res.get("job_id")
    if no_wait or not job_id:
        if json_output:
            print(json.dumps({"publish": pub_res, "subscribers": sub_res}, indent=2))
            return
        if job_id:
            console.print(f"[bold cyan]🚀 Queued subscriber rollout job:[/bold cyan] {job_id}")
            console.print(f"   Attach anytime: [cyan]valstorm app deploy-status {job_id} --follow[/cyan]")
        else:
            console.print("[bold green]✓ Updated subscribing organizations.[/bold green]")
        return

    if not json_output:
        console.print(f"[bold cyan]🚀 Started subscriber rollout job:[/bold cyan] {job_id} (concurrency={concurrency})")
        console.print(f"   [dim]Re-attach anytime: valstorm app deploy-status {job_id} --follow[/dim]")

    report, detached = follow_deployment(sdk, job_id, json_output=json_output, console=console)
    if json_output:
        print(json.dumps({"publish": pub_res, "deployment": report}, indent=2))
    if not detached and report.get("status") in ("failed", "completed_with_errors"):
        raise typer.Exit(1)


@app_cmds.command("update-subscribers")
@requires_auth
def update_subscribers_cmd(
    app_id: str = typer.Argument(..., help="App ID to roll out to all subscribing organizations."),
    no_wait: bool = typer.Option(False, "--no-wait", help="Return immediately after queueing."),
    concurrency: int = typer.Option(12, "--concurrency", min=1, max=30, help="Concurrent tenant rollouts."),
    include_sandboxes: bool = typer.Option(
        True,
        "--include-sandboxes/--no-sandboxes",
        help="Include subscribed sandbox organizations.",
    ),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key", help="Optional idempotency key."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """Queue a background Go fleet rollout for all organizations subscribed to an app."""
    try:
        sub_res = sdk.apps.update_subscribers(
            app_id,
            concurrency=concurrency,
            include_sandboxes=include_sandboxes,
            trigger_source="cli",
            idempotency_key=idempotency_key,
        )
    except ValstormError as e:
        console.print(f"[bold red]Rollout failed to start:[/bold red] {e}")
        raise typer.Exit(1)

    job_id = sub_res.get("deployment_job_id") or sub_res.get("job_id")
    if no_wait or not job_id:
        if json_output:
            print(json.dumps(sub_res, indent=2))
            return
        console.print(f"[bold cyan]🚀 Queued subscriber rollout job:[/bold cyan] {job_id}")
        console.print(f"   Attach anytime: [cyan]valstorm app deploy-status {job_id} --follow[/cyan]")
        return

    if not json_output:
        console.print(f"[bold cyan]🚀 Started subscriber rollout job:[/bold cyan] {job_id} (concurrency={concurrency})")
        console.print(f"   [dim]Re-attach anytime: valstorm app deploy-status {job_id} --follow[/dim]")

    report, detached = follow_deployment(sdk, job_id, json_output=json_output, console=console)
    if json_output:
        print(json.dumps(report, indent=2))
    if not detached and report.get("status") in ("failed", "completed_with_errors"):
        raise typer.Exit(1)


@app_cmds.command("deploy-status")
@requires_auth
def deploy_status_cmd(
    job_id: str = typer.Argument(..., help="Deployment job ID (e.g. djob_...)."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Attach and stream realtime progress until completion."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """Inspect status or re-attach live progress for a background app deployment job."""
    try:
        if follow:
            report, detached = follow_deployment(sdk, job_id, json_output=json_output, console=console)
            if json_output:
                print(json.dumps(report, indent=2))
            if not detached and report.get("status") in ("failed", "completed_with_errors"):
                raise typer.Exit(1)
            return

        report = sdk.apps.get_deployment(job_id)
    except ValstormError as e:
        console.print(f"[bold red]Error fetching deployment {job_id}:[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(report, indent=2))
        return
    render_deployment_report(report, console)


@app_cmds.command("deploy-retry")
@requires_auth
def deploy_retry_cmd(
    job_id: str = typer.Argument(..., help="Parent deployment job ID to retry failed organizations from."),
    no_wait: bool = typer.Option(False, "--no-wait", help="Return immediately after queueing."),
    concurrency: Optional[int] = typer.Option(None, "--concurrency", min=1, max=30, help="Override concurrency."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """Retry only failed organizations from a previous rollout job without re-running succeeded orgs."""
    try:
        res = sdk.apps.retry_failed_deployment(job_id, concurrency=concurrency)
    except ValstormError as e:
        console.print(f"[bold red]Retry failed:[/bold red] {e}")
        raise typer.Exit(1)

    new_job_id = res.get("deployment_job_id") or res.get("job_id")
    if no_wait or not new_job_id:
        if json_output:
            print(json.dumps(res, indent=2))
            return
        console.print(f"[bold cyan]🔄 Queued retry job:[/bold cyan] {new_job_id} (parent: {job_id})")
        console.print(f"   Attach anytime: [cyan]valstorm app deploy-status {new_job_id} --follow[/cyan]")
        return

    if not json_output:
        console.print(f"[bold cyan]🔄 Started retry rollout job:[/bold cyan] {new_job_id} (parent: {job_id})")

    report, detached = follow_deployment(sdk, new_job_id, json_output=json_output, console=console)
    if json_output:
        print(json.dumps(report, indent=2))
    if not detached and report.get("status") in ("failed", "completed_with_errors"):
        raise typer.Exit(1)


@app_cmds.command("deploy-cancel")
@requires_auth
def deploy_cancel_cmd(
    job_id: str = typer.Argument(..., help="Active deployment job ID to cancel."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """Cooperatively cancel an active deployment rollout job."""
    try:
        report = sdk.apps.cancel_deployment(job_id)
    except ValstormError as e:
        console.print(f"[bold red]Cancel failed:[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(report, indent=2))
        return
    render_deployment_report(report, console)


@app_cmds.command("deployments")
@requires_auth
def list_deployments_cmd(
    app_id: Optional[str] = typer.Option(None, "--app", help="Filter by app ID."),
    status_filter: Optional[str] = typer.Option(None, "--status", help="Comma-separated status filter."),
    limit: int = typer.Option(20, "--limit", min=1, max=100, help="Max jobs to display."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    sdk: ValstormClient = None,  # type: ignore
):
    """List recent and active multi-tenant app deployment rollout jobs."""
    try:
        jobs = sdk.apps.list_deployments(app_id=app_id, status=status_filter, limit=limit)
    except ValstormError as e:
        console.print(f"[bold red]Error listing deployments:[/bold red] {e}")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(jobs, indent=2))
        return

    if not jobs:
        console.print("[dim]No deployment jobs found.[/dim]")
        return

    table = Table(title="App Deployment Rollout Jobs")
    table.add_column("Job ID", style="cyan")
    table.add_column("App", style="bold")
    table.add_column("Version")
    table.add_column("Status")
    table.add_column("Orgs (OK/Fail/Total)", justify="right")
    table.add_column("Created", style="dim")

    for j in jobs:
        c = j.get("counts") or {}
        st = str(j.get("status") or "")
        st_color = {
            "completed": "green",
            "completed_with_errors": "yellow",
            "failed": "red",
            "running": "cyan",
            "queued": "blue",
        }.get(st, "white")
        table.add_row(
            str(j.get("job_id") or ""),
            str(j.get("app_name") or j.get("app_id") or ""),
            str(j.get("app_version") or ""),
            f"[{st_color}]{st}[/{st_color}]",
            f"{c.get('succeeded', 0)}/{c.get('failed', 0)}/{c.get('total_orgs', 0)}",
            str(j.get("created_date") or "")[:19],
        )
    console.print(table)
