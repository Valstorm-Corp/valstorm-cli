import asyncio
import json
import sys
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from .auth import ValstormAuth, get_api_base_url
from .vfs_cmds import handle_error, handle_local_error, handle_network_error

search_cli_app = typer.Typer(help="Search and Ask across Valstorm VFS and Workspace", no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def _format_score_bar(score: float) -> str:
    """Renders a 10-block colored score bar."""
    clamped = max(0.0, min(1.0, score))
    filled = int(round(clamped * 10))
    empty = 10 - filled
    pct = int(round(clamped * 100))

    if clamped >= 0.90:
        color = "green"
    elif clamped >= 0.70:
        color = "cyan"
    elif clamped >= 0.50:
        color = "yellow"
    else:
        color = "red"

    bar = "█" * filled + "░" * empty
    return f"[{color}]{bar}[/{color}] {pct}%"


def _format_match_badge(match_type: str) -> str:
    """Renders styled match type badges."""
    m = (match_type or "").lower()
    if m == "exact":
        return "[bold black on green] EXACT [/bold black on green]"
    elif m == "semantic":
        return "[bold white on blue] SEMANTIC [/bold white on blue]"
    elif m == "hybrid":
        return "[bold white on magenta] HYBRID [/bold white on magenta]"
    elif m == "vault":
        return "[bold black on yellow] VAULT [/bold black on yellow]"
    return f"[dim]{match_type.upper()}[/dim]"


def _human_size(num_bytes: Optional[int]) -> str:
    if num_bytes is None or num_bytes == 0:
        return "-"
    n = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(n) < 1024.0:
            return f"{n:3.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def _render_search_table(query: str, mode: str, results: list, exec_time: float):
    header_panel = Panel(
        Text.from_markup(f"Query: [bold cyan]\"{query}\"[/bold cyan]  •  Mode: [dim]{mode}[/dim]"),
        title=f" Valstorm Search Results ({len(results)} matches in {exec_time:.1f}ms) ",
        title_align="left",
        border_style="cyan",
    )
    console.print(header_panel)

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Match", width=11)
    table.add_column("Score", width=16)
    table.add_column("File / Details", ratio=1)
    table.add_column("Size", width=10, justify="right")

    for idx, item in enumerate(results, start=1):
        badge = _format_match_badge(item.get("match_type", "hybrid"))
        score_bar = _format_score_bar(item.get("score", 0.0))
        name = item.get("name", "Unknown")
        loc = item.get("location", "/")
        fid = item.get("id", "")
        size_str = _human_size(item.get("size"))
        snippet = item.get("snippet")

        file_cell = Text()
        file_cell.append(f"📁 {loc}\n", style="dim")
        file_cell.append(f"📄 {name} ", style="bold white")
        if fid:
            file_cell.append(f"({fid})\n", style="dim")
        else:
            file_cell.append("\n")
        if snippet:
            clean_snippet = snippet.replace("\n", " ").strip()
            if len(clean_snippet) > 160:
                clean_snippet = clean_snippet[:157] + "..."
            file_cell.append(f"   Snippet: {clean_snippet}", style="italic bright_black")

        table.add_row(str(idx), badge, score_bar, file_cell, size_str)
        if idx < len(results):
            table.add_row("", "", "", "", "")

    console.print(table)
    console.print("[dim]Tip: Use 'valstorm ask \"<question>\"' to generate conversational answers with source citations.[/dim]\n")


def _render_citations_table(citations_data: list):
    if not citations_data:
        return
    citation_table = Table(box=None, show_header=False, padding=(0, 1))
    citation_table.add_column("Ref", width=5, style="bold cyan")
    citation_table.add_column("Source Document", style="white")

    for idx, src in enumerate(citations_data, start=1):
        name = src.get("file_name", "Document")
        loc = src.get("location", "")
        score = src.get("score", 0.0)
        snippet = src.get("snippet", "").strip()

        cell = Text()
        cell.append(f"{name} ", style="bold")
        cell.append(f"({loc}) • Match {int(score * 100)}%\n", style="dim")
        if snippet:
            cell.append(f"\"{snippet}\"", style="italic bright_black")

        citation_table.add_row(f"[{idx}]", cell)

    console.print(Panel(citation_table, title=" Grounded Sources & Citations ", border_style="dim"))


async def _parse_sse_stream(response: httpx.Response) -> AsyncGenerator[Dict[str, Any], None]:
    """Parses standard Server-Sent Events (SSE) data lines."""
    current_event = "message"
    async for line in response.aiter_lines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.replace("event:", "", 1).strip()
        elif line.startswith("data:"):
            raw_data = line.replace("data:", "", 1).strip()
            try:
                parsed_data = json.loads(raw_data)
            except json.JSONDecodeError:
                parsed_data = raw_data
            yield {"event": current_event, "data": parsed_data}
            current_event = "message"


async def stream_search_events(
    auth: ValstormAuth,
    query: str,
    vault_id: Optional[str] = None,
    limit: int = 5,
    enable_rag: bool = True,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Connects to POST /v1/search/stream and yields parsed SSE event objects."""
    base_url = get_api_base_url(auth.env)
    payload = {
        "query": query,
        "vault_id": vault_id,
        "limit": limit,
        "enable_rag": enable_rag,
    }

    headers = {
        "Authorization": f"Bearer {auth.access_token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            async with client.stream("POST", "/search/stream", json=payload, headers=headers) as response:
                if response.status_code == 401:
                    # Token expired; attempt synchronous refresh
                    if auth.refresh_auth():
                        headers["Authorization"] = f"Bearer {auth.access_token}"
                        async with client.stream("POST", "/search/stream", json=payload, headers=headers) as retry_res:
                            if retry_res.status_code != 200:
                                body = await retry_res.aread()
                                yield {"event": "error", "data": {"status_code": retry_res.status_code, "message": body.decode()}}
                                return
                            async for event in _parse_sse_stream(retry_res):
                                yield event
                        return
                    else:
                        yield {"event": "error", "data": {"status_code": 401, "message": "Unauthorized. Please run 'valstorm login'."}}
                        return

                if response.status_code != 200:
                    body = await response.aread()
                    yield {"event": "error", "data": {"status_code": response.status_code, "message": body.decode()}}
                    return

                async for event in _parse_sse_stream(response):
                    yield event
    except httpx.RequestError as e:
        yield {"event": "error", "data": {"status_code": 2, "message": f"Network error: {e}"}}


@search_cli_app.command("query")
def search_command(
    query: str = typer.Argument(..., help="Search terms, filename, or semantic query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results to return (1-50)"),
    semantic_only: bool = typer.Option(False, "--semantic-only", help="Filter strictly by semantic vector similarity"),
    exact_only: bool = typer.Option(False, "--exact-only", help="Filter strictly by exact metadata match"),
    vault: Optional[str] = typer.Option(None, "--vault", "-v", help="Scope search to a specific Vault ID or path"),
    file_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by file extension (pdf, md, docx, etc.)"),
    min_score: float = typer.Option(0.0, "--min-score", help="Minimum similarity/RRF score threshold (0.0 - 1.0)"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON data"),
    plain_output: bool = typer.Option(False, "--plain", "-p", help="Output plain tab-separated text for pipelines"),
):
    """Search files, metadata, and document vector chunks across the workspace."""
    if semantic_only and exact_only:
        handle_local_error("Cannot specify both --semantic-only and --exact-only simultaneously.", json_output, exit_code=1)

    auth = ValstormAuth()
    if not auth.access_token:
        handle_local_error("Not authenticated. Please run 'valstorm login' first.", json_output, exit_code=3)

    mode = "hybrid"
    if semantic_only:
        mode = "semantic_only"
    elif exact_only:
        mode = "exact_only"

    payload = {
        "query": query,
        "limit": limit,
        "vault_id": vault,
        "file_type": file_type,
        "mode": mode,
        "min_score": min_score,
    }

    try:
        client = auth.get_client(timeout=15.0)
        res = client.post("/search", json=payload)
        handle_error(res, json_output)
        data = res.json()
    except httpx.RequestError as e:
        handle_network_error(e, json_output)

    results = data.get("results", [])
    exec_time = data.get("execution_time_ms", 0.0)

    # 1. JSON Output mode
    if json_output:
        print(json.dumps(data, indent=2))
        return

    # 2. Plain TSV Output mode (fzf / awk friendly)
    if plain_output:
        for r in results:
            score = r.get("score", 0.0)
            mtype = r.get("match_type", "unknown")
            fid = r.get("id", "")
            loc = r.get("location", "")
            name = r.get("name", "")
            print(f"{score:.3f}\t{mtype}\t{fid}\t{loc}\t{name}")
        return

    # 3. Interactive Rich Table UI
    if not results:
        console.print(f"\n[yellow]No matching documents or files found for query:[/yellow] [bold]{query}[/bold]\n")
        return

    _render_search_table(query, mode, results, exec_time)


async def _stream_rag_answer(
    auth: ValstormAuth,
    question: str,
    vault: Optional[str],
    limit: int,
    no_citations: bool,
    raw_mode: bool,
):
    if raw_mode:
        async for msg in stream_search_events(auth, question, vault_id=vault, limit=limit, enable_rag=True):
            event = msg.get("event")
            data = msg.get("data", {})
            if event == "ai_chunk":
                delta = data.get("delta", "") if isinstance(data, dict) else str(data)
                sys.stdout.write(delta)
                sys.stdout.flush()
            elif event == "error":
                err_msg = data.get("message", "Unknown stream error") if isinstance(data, dict) else str(data)
                err_console.print(f"[bold red]Stream Error:[/bold red] {err_msg}")
                sys.exit(2)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return

    # Rich Live Streaming UX
    console.print(Panel(
        Text.from_markup(f"[bold white]Question:[/bold white] {question}"),
        title=" Valstorm Workspace AI ",
        border_style="magenta",
    ))

    accumulated_markdown = ""
    citations_data = []
    spinner = Spinner("dots", text="[italic cyan]Searching workspace knowledge & synthesizing answer...[/italic cyan]")

    with Live(spinner, console=console, refresh_per_second=15) as live:
        async for msg in stream_search_events(auth, question, vault_id=vault, limit=limit, enable_rag=True):
            event = msg.get("event")
            data = msg.get("data", {})

            if event in ("metadata_results", "blended_hits"):
                metadata_count = len(data.get("results", [])) if isinstance(data, dict) else 0
                live.update(Spinner("dots", text=f"[italic cyan]Grounded with {metadata_count} workspace document chunks...[/italic cyan]"))

            elif event == "ai_chunk":
                delta = data.get("delta", "") if isinstance(data, dict) else str(data)
                accumulated_markdown += delta
                live.update(Markdown(accumulated_markdown))

            elif event == "citations":
                citations_data = data.get("sources", []) if isinstance(data, dict) else []

            elif event == "error":
                live.stop()
                err_msg = data.get("message", "Unknown stream error") if isinstance(data, dict) else str(data)
                console.print(f"[bold red]Stream Error:[/bold red] {err_msg}")
                sys.exit(2)

    # Render Citations Panel
    if citations_data and not no_citations:
        _render_citations_table(citations_data)


async def _async_ask_handler(
    question: str,
    vault: Optional[str],
    limit: int,
    no_citations: bool,
    raw_mode: bool,
    json_output: bool,
):
    """Async execution pipeline for live token streaming and citation rendering."""
    auth = ValstormAuth()
    if not auth.access_token:
        handle_local_error("Not authenticated. Please run 'valstorm login' first.", json_output, exit_code=3)

    if json_output:
        # Non-streaming JSON aggregation
        client = auth.get_client(timeout=30.0)
        try:
            res = client.post("/search", json={"query": question, "limit": limit, "enable_rag": True, "vault_id": vault})
            handle_error(res, json_output=True)
            print(json.dumps(res.json(), indent=2))
        except httpx.RequestError as e:
            handle_network_error(e, json_output=True)
        return

    await _stream_rag_answer(
        auth=auth,
        question=question,
        vault=vault,
        limit=limit,
        no_citations=no_citations,
        raw_mode=raw_mode,
    )


@search_cli_app.command("ask")
def ask_command(
    question: str = typer.Argument(..., help="Natural language question to ask"),
    vault: Optional[str] = typer.Option(None, "--vault", "-v", help="Limit search context to a specific Vault"),
    limit: int = typer.Option(5, "--limit", "-l", help="Number of document chunks for context grounding"),
    no_citations: bool = typer.Option(False, "--no-citations", help="Hide source citations panel"),
    raw: bool = typer.Option(False, "--raw", help="Stream raw text directly without Rich rendering"),
    json_output: bool = typer.Option(False, "--json", help="Return structured JSON answer and sources"),
):
    """Ask natural language questions grounded in workspace documents with streaming AI answers."""
    asyncio.run(_async_ask_handler(question, vault, limit, no_citations, raw, json_output))
