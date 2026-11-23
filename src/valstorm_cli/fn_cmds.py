import json
from pathlib import Path
from typing import Any, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

from .auth import requires_auth

console = Console()
fn_app = typer.Typer(help="Manage, validate, and execute Open Valstorm serverless Python functions.")


def _parse_json_inputs(input_json: Optional[str], input_file: Optional[str]) -> Optional[dict[str, Any]]:
    if input_file:
        p = Path(input_file)
        if not p.exists():
            console.print(f"[bold red]Error:[/bold red] Input file '{input_file}' not found.")
            raise typer.Exit(1)
        try:
            parsed = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Invalid JSON in '{input_file}':[/bold red] {e}")
            raise typer.Exit(1)
    elif input_json:
        try:
            parsed = json.loads(input_json)
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Invalid JSON in --input:[/bold red] {e}")
            raise typer.Exit(1)
    else:
        return None

    if not isinstance(parsed, dict):
        console.print("[bold red]Error:[/bold red] Function inputs must be a JSON object.")
        raise typer.Exit(1)
    return parsed


@fn_app.command("list")
@requires_auth
def list_functions(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    List serverless functions in the organization.
    """
    res = client.get("/function", timeout=30.0)
    if res.status_code != 200:
        console.print(f"[bold red]Failed to list functions ({res.status_code}):[/bold red] {res.text}")
        raise typer.Exit(1)

    data = res.json()
    items = data if isinstance(data, list) else data.get("functions", data.get("records", []))

    if json_output:
        print(json.dumps(items, indent=2))
        return

    if not items:
        console.print("[yellow]No functions found.[/yellow]")
        return

    table = Table(title="Valstorm Functions")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("File", style="green")
    table.add_column("App", style="magenta")

    for fn in items:
        if isinstance(fn, dict):
            app_val = fn.get("app")
            if isinstance(app_val, dict):
                app_val = app_val.get("name") or app_val.get("id") or ""
            table.add_row(
                str(fn.get("id", "")),
                str(fn.get("name", "")),
                str(fn.get("file_name", "")),
                str(app_val or ""),
            )
    console.print(table)


@fn_app.command("validate")
@requires_auth
def validate_function(
    file_path: Path = typer.Argument(..., help="Path to a local Python function file to AST-validate and dry-run."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Function name override (defaults to file stem)."),
    input_json: Optional[str] = typer.Option(None, "--input", "-i", help="JSON object of test inputs."),
    input_file: Optional[str] = typer.Option(None, "--input-file", "-f", help="Path to JSON file of test inputs."),
    timeout: float = typer.Option(30.0, "--timeout", help="Execution timeout in seconds (0.1-60)."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Dry-run a local Python file through Open Valstorm's AST gatekeeper and sandbox without persisting.
    """
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        raise typer.Exit(1)

    inputs = _parse_json_inputs(input_json, input_file)
    payload: dict[str, Any] = {
        "code": file_path.read_text(encoding="utf-8"),
        "function_name": name or file_path.stem,
        "timeout": timeout,
    }
    if inputs is not None:
        payload["inputs"] = inputs

    res = client.post("/function/validate", json=payload, timeout=max(timeout + 10.0, 30.0))
    if res.status_code not in (200, 201):
        console.print(f"[bold red]Validation request failed ({res.status_code}):[/bold red] {res.text}")
        raise typer.Exit(1)

    data = res.json()
    if json_output:
        print(json.dumps(data, indent=2))
        if not data.get("valid", data.get("success", True)):
            raise typer.Exit(1)
        return

    is_valid = data.get("valid", data.get("success", False))
    if is_valid:
        console.print(f"[bold green]✓ Function '{file_path.name}' passed AST validation and dry-run.[/bold green]")
        if "result" in data and data["result"] is not None:
            console.print(json.dumps(data["result"], indent=2))
    else:
        console.print(f"[bold red]✗ Validation failed for '{file_path.name}':[/bold red]")
        if data.get("error"):
            console.print(f"  {data['error']}")
        for err in data.get("errors") or []:
            console.print(f"  - {err}")
        raise typer.Exit(1)


@fn_app.command("run")
@requires_auth
def run_function(
    target: str = typer.Argument(..., help="Local .py file path, function ID (func_...), or function name."),
    input_json: Optional[str] = typer.Option(None, "--input", "-i", help="JSON object of function inputs."),
    input_file: Optional[str] = typer.Option(None, "--input-file", "-f", help="Path to JSON file of function inputs."),
    timeout: float = typer.Option(30.0, "--timeout", help="Execution timeout in seconds (0.1-60)."),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile name."),
    env: Optional[str] = typer.Option(None, "--env", "-e", help="Target environment."),
    client: httpx.Client = None,  # type: ignore
):
    """
    Execute a serverless function by local `.py` file, function ID, or function name.
    """
    inputs = _parse_json_inputs(input_json, input_file)
    payload: dict[str, Any] = {"timeout": timeout}

    target_path = Path(target)
    if target_path.is_file() and target_path.suffix == ".py":
        payload["code"] = target_path.read_text(encoding="utf-8")
        payload["function_name"] = target_path.stem
    elif target.startswith("func_"):
        payload["function_id"] = target
    else:
        payload["function_name"] = target

    if inputs is not None:
        payload["inputs"] = inputs

    res = client.post("/function/execute", json=payload, timeout=max(timeout + 10.0, 30.0))
    if res.status_code not in (200, 201):
        console.print(f"[bold red]Function execution failed ({res.status_code}):[/bold red] {res.text}")
        raise typer.Exit(1)

    content_type = res.headers.get("content-type", "")
    if "application/json" in content_type:
        data = res.json()
        print(json.dumps(data, indent=2))
    else:
        if json_output:
            print(json.dumps({"body": res.text, "content_type": content_type}, indent=2))
        else:
            print(res.text)
