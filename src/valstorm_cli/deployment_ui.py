"""Rich realtime progress UI and SSE/polling follower for multi-tenant app rollouts."""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from valstorm import ValstormClient, ValstormError

TERMINAL_STATUSES = frozenset({"completed", "completed_with_errors", "failed", "cancelled"})


def _fmt_duration(ms: float | None) -> str:
    if ms is None:
        return "-"
    secs = float(ms) / 1000.0
    if secs < 60:
        return f"{secs:.1f}s"
    mins = int(secs // 60)
    rem = secs - mins * 60
    return f"{mins}m {rem:.1f}s"


def render_deployment_report(report: dict[str, Any], console: Console) -> None:
    """Renders a structured final deployment report table and retry hint."""
    status = str(report.get("status") or "unknown")
    app_name = report.get("app_name") or report.get("app_id") or "App"
    app_version = report.get("app_version") or "1.0.0"
    job_id = report.get("job_id") or ""
    counts = report.get("counts") or {}
    totals = report.get("totals") or {}
    dur = _fmt_duration(report.get("total_duration_ms"))

    badge_color = {
        "completed": "bold green",
        "completed_with_errors": "bold yellow",
        "failed": "bold red",
        "cancelled": "bold magenta",
    }.get(status, "bold cyan")

    console.print()
    console.print(
        f"[{badge_color}]● Rollout {status.upper()}[/{badge_color}]  "
        f"[bold]{app_name}[/bold] v{app_version}  [dim]({job_id} · {dur})[/dim]"
    )

    summary = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    summary.add_column("Total Orgs", justify="right")
    summary.add_column("Succeeded", justify="right", style="green")
    summary.add_column("Failed", justify="right", style="red")
    summary.add_column("Skipped", justify="right", style="dim")
    summary.add_column("Schemas Applied", justify="right")
    summary.add_column("Records Applied", justify="right")
    summary.add_row(
        str(counts.get("total_orgs", 0)),
        str(counts.get("succeeded", 0)),
        str(counts.get("failed", 0)),
        str(counts.get("skipped", 0)),
        str(totals.get("total_schemas_applied", 0)),
        str(totals.get("total_records_applied", 0)),
    )
    console.print(summary)

    failed_orgs = report.get("failed_orgs") or []
    if failed_orgs:
        console.print()
        err_table = Table(title="Failed Organizations", show_lines=False)
        err_table.add_column("Organization", style="bold")
        err_table.add_column("Org ID", style="dim")
        err_table.add_column("Code", style="yellow")
        err_table.add_column("Error", style="red")
        for fo in failed_orgs:
            err_table.add_row(
                str(fo.get("organization_name") or "-"),
                str(fo.get("organization_id") or "-"),
                str(fo.get("error_code") or "DEPLOYMENT_ERROR"),
                str(fo.get("error_message") or ""),
            )
        console.print(err_table)
        retry_cmd = (report.get("retry") or {}).get("cli_command") or f"valstorm app deploy-retry {job_id}"
        console.print(f"\n[bold yellow]Retry failed organizations:[/bold yellow] [cyan]{retry_cmd}[/cyan]")


def _build_live_renderable(
    progress: Progress,
    org_lines: dict[str, dict[str, Any]],
    max_visible: int = 12,
) -> Group:
    items: list[Any] = [progress]
    # Show running orgs first, then most recently updated finished orgs
    running = [v for v in org_lines.values() if v.get("state") == "running"]
    finished = [v for v in org_lines.values() if v.get("state") != "running"]
    visible = (finished[-max(0, max_visible - len(running)) :] + running)[-max_visible:]

    for entry in visible:
        state = entry.get("state")
        name = entry.get("name", "")
        org_id = entry.get("org_id", "")
        detail = entry.get("detail", "")
        line = Text()
        if state == "succeeded":
            line.append("  ✓ ", style="bold green")
            line.append(f"{name} ", style="white")
            line.append(f"({org_id})  ", style="dim")
            line.append(detail, style="green")
        elif state == "failed":
            line.append("  ✗ ", style="bold red")
            line.append(f"{name} ", style="white")
            line.append(f"({org_id})  ", style="dim")
            line.append(detail, style="red")
        elif state == "skipped":
            line.append("  ↷ ", style="dim")
            line.append(f"{name} ", style="dim")
            line.append(f"({org_id})  {detail}", style="dim")
        else:
            line.append("  ⠋ ", style="bold cyan")
            line.append(f"{name} ", style="white")
            line.append(f"({org_id})  ", style="dim")
            line.append(detail, style="cyan")
        items.append(line)
    return Group(*items)


def follow_deployment(
    sdk: ValstormClient,
    job_id: str,
    *,
    json_output: bool = False,
    console: Console | None = None,
    poll_interval: float = 2.0,
    max_sse_retries: int = 3,
) -> tuple[dict[str, Any], bool]:
    """
    Follows a durable rollout job to completion via SSE (with automatic Last-Event-ID reconnect
    and polling fallback).

    Returns `(final_report, detached)`:
      - `detached=True` if user pressed Ctrl+C (rollout continues running on server).
    """
    con = console or Console()
    initial = sdk.apps.get_deployment(job_id)
    if initial.get("status") in TERMINAL_STATUSES:
        if not json_output:
            render_deployment_report(initial, con)
        return initial, False

    app_name = str(initial.get("app_name") or initial.get("app_id") or "App")
    app_version = str(initial.get("app_version") or "1.0.0")
    counts = initial.get("counts") or {}
    total_orgs = int(counts.get("total_orgs") or 0)

    org_lines: dict[str, dict[str, Any]] = {}
    for r in initial.get("org_results") or []:
        oid = str(r.get("organization_id") or "")
        st = str(r.get("status") or "pending")
        if st == "succeeded":
            org_lines[oid] = {
                "org_id": oid,
                "name": r.get("organization_name", oid),
                "state": "succeeded",
                "detail": f"{r.get('schemas_synced', 0)} schemas · {r.get('records_applied', 0)} records  {_fmt_duration(r.get('duration_ms'))}",
            }
        elif st == "failed":
            org_lines[oid] = {
                "org_id": oid,
                "name": r.get("organization_name", oid),
                "state": "failed",
                "detail": str(r.get("error_message") or r.get("error_code") or "failed")[:80],
            }
        elif st == "running":
            org_lines[oid] = {
                "org_id": oid,
                "name": r.get("organization_name", oid),
                "state": "running",
                "detail": "Rolling out...",
            }

    use_live_ui = not json_output and con.is_terminal
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.completed}/{task.total} orgs"),
        TimeElapsedColumn(),
        console=con,
    )
    task_id = progress.add_task(
        f"Rolling out {app_name} v{app_version}",
        total=max(total_orgs, 1),
        completed=int(counts.get("completed_orgs") or 0),
    )

    final_report: dict[str, Any] | None = None
    last_event_id: str | None = None
    sse_failures = 0

    def _apply_event(ev_type: str, envelope: dict[str, Any], live: Live | None) -> bool:
        nonlocal final_report
        prog = envelope.get("progress") or {}
        t_orgs = int(prog.get("total_orgs") or 0)
        c_orgs = int(prog.get("completed_orgs") or 0)
        if t_orgs > 0:
            progress.update(task_id, total=t_orgs, completed=c_orgs)

        data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
        oid = str(data.get("organization_id") or "")
        oname = str(data.get("organization_name") or oid)

        if ev_type == "org_started" and oid:
            org_lines[oid] = {
                "org_id": oid,
                "name": oname,
                "state": "running",
                "detail": f"Starting ({data.get('schemas_total', 0)} schemas)...",
            }
        elif ev_type == "org_schema_synced" and oid:
            org_lines[oid] = {
                "org_id": oid,
                "name": oname,
                "state": "running",
                "detail": f"Syncing schema {data.get('schemas_synced', 0)}/{data.get('schemas_total', 0)} ({data.get('schema_api_name', '')})...",
            }
        elif ev_type == "org_completed" and oid:
            org_lines[oid] = {
                "org_id": oid,
                "name": oname,
                "state": "succeeded",
                "detail": f"{data.get('schemas_synced', 0)} schemas · {data.get('records_applied', 0)} records  {_fmt_duration(data.get('duration_ms'))}",
            }
        elif ev_type == "org_failed" and oid:
            org_lines[oid] = {
                "org_id": oid,
                "name": oname,
                "state": "failed",
                "detail": f"{data.get('error_code', 'ERROR')}: {str(data.get('error_message', ''))[:72]}",
            }
        elif ev_type == "job_completed":
            if isinstance(data, dict) and data.get("job_id"):
                final_report = data
            return True

        if live is not None:
            live.update(_build_live_renderable(progress, org_lines))
        return False

    live_ctx = Live(_build_live_renderable(progress, org_lines), console=con, refresh_per_second=8) if use_live_ui else None

    try:
        if live_ctx is not None:
            live_ctx.start()

        # 1. Primary SSE streaming loop with automatic Last-Event-ID reconnect
        while sse_failures <= max_sse_retries and final_report is None:
            try:
                for ev in sdk.apps.stream_deployment(job_id, last_event_id=last_event_id):
                    if ev.id:
                        last_event_id = ev.id
                    envelope = ev.data if isinstance(ev.data, dict) else {}
                    ev_type = str(envelope.get("type") or ev.event or "message")
                    done = _apply_event(ev_type, envelope, live_ctx)
                    if done:
                        break
                # Stream ended: check authoritative PG snapshot
                snap = sdk.apps.get_deployment(job_id)
                if snap.get("status") in TERMINAL_STATUSES:
                    final_report = snap
                    break
                sse_failures += 1
            except (ValstormError, OSError):
                sse_failures += 1
                if sse_failures <= max_sse_retries:
                    time.sleep(min(1.0 * sse_failures, 3.0))

        # 2. Polling fallback if SSE could not hold connection
        while final_report is None:
            snap = sdk.apps.get_deployment(job_id)
            snap_counts = snap.get("counts") or {}
            if snap_counts.get("total_orgs"):
                progress.update(
                    task_id,
                    total=int(snap_counts["total_orgs"]),
                    completed=int(snap_counts.get("completed_orgs") or 0),
                )
            for r in snap.get("org_results") or []:
                oid = str(r.get("organization_id") or "")
                st = str(r.get("status") or "")
                if st in ("succeeded", "failed", "running", "skipped") and oid:
                    detail = (
                        f"{r.get('schemas_synced', 0)} schemas · {_fmt_duration(r.get('duration_ms'))}"
                        if st == "succeeded"
                        else str(r.get("error_message") or r.get("skip_reason") or "Rolling out...")[:72]
                    )
                    org_lines[oid] = {
                        "org_id": oid,
                        "name": r.get("organization_name", oid),
                        "state": st,
                        "detail": detail,
                    }
            if live_ctx is not None:
                live_ctx.update(_build_live_renderable(progress, org_lines))
            if snap.get("status") in TERMINAL_STATUSES:
                final_report = snap
                break
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        if live_ctx is not None:
            live_ctx.stop()
        if not json_output:
            con.print(
                f"\n[yellow]Detached from rollout {job_id} (still running on server).[/yellow]\n"
                f"Resume anytime: [cyan]valstorm app deploy-status {job_id} --follow[/cyan]"
            )
        return sdk.apps.get_deployment(job_id), True
    finally:
        if live_ctx is not None:
            live_ctx.stop()

    report = final_report or sdk.apps.get_deployment(job_id)
    if not json_output:
        render_deployment_report(report, con)
    return report, False
