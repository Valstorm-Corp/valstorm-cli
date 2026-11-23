import json
from pathlib import Path
from typing import Any, List, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

from .auth import requires_auth

console = Console()
rpc_app = typer.Typer(help="Discover and invoke Open Valstorm PlatformContext and plugin RPC methods.")


def _parse_arg_value(raw: str) -> Any:
    """Parse CLI key=value values as JSON when valid (ints, bools, lists, objects), else string."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _build_rpc_payload(
    data_json: Optional[str],
    data_file: Optional[str],
    args: Optional[List[str]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    if data_file:
        p = Path(data_file)
        if not p.exists():
            console.print(f"[bold red]Error:[/bold red] Data file '{data_file}' not found.")
            raise typer.Exit(1)
        try:
            loaded = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Invalid JSON in '{data_file}':[/bold red] {e}")
            raise typer.Exit(1)
        if not isinstance(loaded, dict):
            console.print("[bold red]Error:[/bold red] RPC payload must be a JSON object.")
            raise typer.Exit(1)
        payload.update(loaded)

    if data_json:
        try:
            loaded = json.loads(data_json)
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Invalid JSON in --data:[/bold red] {e}")
            raise typer.Exit(1)
        if not isinstance(loaded, dict):
            console.print("[bold red]Error:[/bold red] RPC payload must be a JSON object.")
            raise typer.Exit(1)
        payload.update(loaded)

    for pair in args or []:
        if "=" not in pair:
            console.print(f"[bold red]Invalid --arg '{pair}':[/bold red] expected key=value.")
            raise typer.Exit(1)
        key, raw_val = pair.split("=", 1)
        payload[key.strip()] = _parse_arg_value(raw_val)

    return payload


@rpc_app.command("list")
@requires_auth
def list_rpc_methods(
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Filter by namespace/plugin (e.g., quickbooks, stripe, utils)."),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Search substring across method names and docstrings."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    List all callable PlatformContext and active plugin RPC methods.
    """
    params: dict[str, Any] = {}
    if namespace:
        params["namespace"] = namespace
    if query:
        params["q"] = query

    res = client.get("/platform/methods", params=params, timeout=30.0)
    if res.status_code != 200:
        console.print(f"[bold red]Failed to list RPC methods ({res.status_code}):[/bold red] {res.text}")
        raise typer.Exit(1)

    data = res.json()
    if json_output:
        print(json.dumps(data, indent=2))
        return

    methods = data.get("methods", []) if isinstance(data, dict) else data
    if not methods:
        console.print("[yellow]No matching RPC methods found.[/yellow]")
        return

    table = Table(title=f"Platform RPC Methods ({len(methods)})")
    table.add_column("Target", style="cyan")
    table.add_column("Signature", style="green")
    table.add_column("Scope", style="magenta")
    table.add_column("Description", style="white")

    for m in methods:
        if isinstance(m, dict):
            target = m.get("target") or m.get("name") or ""
            sig = m.get("signature") or ""
            scope = m.get("scope") or ""
            desc = (m.get("description") or m.get("doc") or "").splitlines()[0] if (m.get("description") or m.get("doc")) else ""
            table.add_row(str(target), str(sig)[:50], str(scope), desc[:80])
    console.print(table)


@rpc_app.command("call")
@requires_auth
def call_rpc_method(
    target: str = typer.Argument(..., help="Dotted RPC target path (e.g., utils.ping, github.list_repositories)."),
    data: Optional[str] = typer.Option(None, "--data", "-d", help="JSON object of keyword arguments."),
    data_file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to JSON file of keyword arguments."),
    arg: Optional[List[str]] = typer.Option(None, "--arg", "-a", help="Key=value argument (repeatable; JSON-parsed when valid)."),
    raw: bool = typer.Option(False, "--raw", help="Print the full RPC response envelope instead of just `result`."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Invoke any PlatformContext or active plugin RPC method via `/v1/platform/invoke/{target}`.
    """
    clean_target = target.strip().strip("/")
    payload = _build_rpc_payload(data, data_file, arg)

    res = client.post(f"/platform/invoke/{clean_target}", json=payload, timeout=60.0)
    if res.status_code not in (200, 201):
        console.print(f"[bold red]RPC call '{clean_target}' failed ({res.status_code}):[/bold red] {res.text}")
        raise typer.Exit(1)

    body = res.json()
    if raw or not isinstance(body, dict) or "result" not in body:
        print(json.dumps(body, indent=2))
    else:
        print(json.dumps(body["result"], indent=2))
