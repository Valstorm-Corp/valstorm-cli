import json
import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, AsyncMock, patch

from valstorm_cli.main import app
from valstorm_cli.search_cmds import (
    _format_score_bar,
    _format_match_badge,
    _human_size,
    _parse_sse_stream,
    _render_citations_table,
    stream_search_events,
)

runner = CliRunner()


def test_format_score_bar():
    high = _format_score_bar(0.95)
    assert "green" in high
    assert "95%" in high

    mid_high = _format_score_bar(0.75)
    assert "cyan" in mid_high
    assert "75%" in mid_high

    mid = _format_score_bar(0.55)
    assert "yellow" in mid
    assert "55%" in mid

    low = _format_score_bar(0.30)
    assert "red" in low
    assert "30%" in low


def test_format_match_badge():
    assert "EXACT" in _format_match_badge("exact")
    assert "SEMANTIC" in _format_match_badge("semantic")
    assert "HYBRID" in _format_match_badge("hybrid")
    assert "VAULT" in _format_match_badge("vault")
    assert "CUSTOM" in _format_match_badge("custom")
    assert "[dim][/dim]" == _format_match_badge("")


def test_human_size():
    assert _human_size(None) == "-"
    assert _human_size(0) == "-"
    assert "500.0 B" in _human_size(500)
    assert "1.5 KB" in _human_size(1536)
    assert "1.5 MB" in _human_size(1572864)


def test_search_mutual_exclusion():
    result = runner.invoke(app, ["search", "test", "--semantic-only", "--exact-only"])
    assert result.exit_code == 1
    assert "Cannot specify both --semantic-only and --exact-only" in result.output


def test_search_invalid_limit():
    result = runner.invoke(app, ["search", "test", "--limit", "not_a_number"])
    assert result.exit_code == 2


@patch("valstorm_cli.search_cmds.ValstormAuth")
def test_search_unauthenticated(mock_auth_cls):
    mock_auth = MagicMock()
    mock_auth.access_token = None
    mock_auth_cls.return_value = mock_auth

    result = runner.invoke(app, ["search", "test"])
    assert result.exit_code == 3
    assert "Not authenticated" in result.output


@patch("valstorm_cli.search_cmds.ValstormAuth")
def test_search_json_output(mock_auth_cls):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_client = MagicMock()
    mock_auth.get_client.return_value = mock_client
    mock_auth_cls.return_value = mock_auth

    fake_response_data = {
        "intent": "search",
        "query": "contracts",
        "count": 1,
        "execution_time_ms": 42.0,
        "results": [
            {
                "id": "fil_123",
                "name": "contracts.pdf",
                "score": 0.92,
                "match_type": "hybrid",
                "location": "/Legal/contracts.pdf",
                "size": 1024,
                "snippet": "termination clause text",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response_data
    mock_client.post.return_value = mock_resp

    result = runner.invoke(app, ["search", "contracts", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["count"] == 1
    assert parsed["results"][0]["id"] == "fil_123"


@patch("valstorm_cli.search_cmds.ValstormAuth")
def test_search_plain_output(mock_auth_cls):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_client = MagicMock()
    mock_auth.get_client.return_value = mock_client
    mock_auth_cls.return_value = mock_auth

    fake_response_data = {
        "intent": "search",
        "query": "agreement",
        "count": 1,
        "execution_time_ms": 30.0,
        "results": [
            {
                "id": "fil_999",
                "name": "agreement.pdf",
                "score": 0.88,
                "match_type": "semantic",
                "location": "/Legal/agreement.pdf",
                "size": 2048,
                "snippet": "agreement snippet",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response_data
    mock_client.post.return_value = mock_resp

    result = runner.invoke(app, ["search", "agreement", "--plain"])
    assert result.exit_code == 0
    lines = [l for l in result.output.strip().split("\n") if l]
    assert len(lines) == 1
    cols = lines[0].split("\t")
    assert cols[0] == "0.880"
    assert cols[1] == "semantic"
    assert cols[2] == "fil_999"
    assert cols[3] == "/Legal/agreement.pdf"
    assert cols[4] == "agreement.pdf"


@patch("valstorm_cli.search_cmds.ValstormAuth")
def test_search_table_render(mock_auth_cls):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_client = MagicMock()
    mock_auth.get_client.return_value = mock_client
    mock_auth_cls.return_value = mock_auth

    fake_response_data = {
        "intent": "search",
        "query": "terms",
        "count": 1,
        "execution_time_ms": 15.0,
        "results": [
            {
                "id": "fil_777",
                "name": "terms.docx",
                "score": 0.95,
                "match_type": "exact",
                "location": "/Docs/terms.docx",
                "size": 4096,
                "snippet": "These are the terms and conditions.",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response_data
    mock_client.post.return_value = mock_resp

    result = runner.invoke(app, ["search", "terms"])
    assert result.exit_code == 0
    assert "terms.docx" in result.output
    assert "Valstorm Search Results" in result.output


@patch("valstorm_cli.search_cmds.ValstormAuth")
def test_search_no_results(mock_auth_cls):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_client = MagicMock()
    mock_auth.get_client.return_value = mock_client
    mock_auth_cls.return_value = mock_auth

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [], "count": 0, "execution_time_ms": 10.0}
    mock_client.post.return_value = mock_resp

    result = runner.invoke(app, ["search", "nonexistent"])
    assert result.exit_code == 0
    assert "No matching documents or files found" in result.output


@patch("valstorm_cli.search_cmds.ValstormAuth")
def test_vfs_search_alias(mock_auth_cls):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_client = MagicMock()
    mock_auth.get_client.return_value = mock_client
    mock_auth_cls.return_value = mock_auth

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [], "count": 0, "execution_time_ms": 10.0}
    mock_client.post.return_value = mock_resp

    result = runner.invoke(app, ["vfs", "search", "test"])
    assert result.exit_code == 0


@patch("valstorm_cli.search_cmds.ValstormAuth")
def test_ask_json_output(mock_auth_cls):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_client = MagicMock()
    mock_auth.get_client.return_value = mock_client
    mock_auth_cls.return_value = mock_auth

    fake_response_data = {
        "intent": "ask",
        "query": "What is the policy?",
        "answer": "The policy requires 30 days notice.",
        "sources": [
            {
                "index": 1,
                "file_id": "fil_123",
                "file_name": "policy.md",
                "location": "/HR/policy.md",
                "score": 0.91,
                "snippet": "Notice requires 30 days.",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response_data
    mock_client.post.return_value = mock_resp

    result = runner.invoke(app, ["ask", "What is the policy?", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["answer"] == "The policy requires 30 days notice."


@patch("valstorm_cli.search_cmds.ValstormAuth")
@patch("valstorm_cli.search_cmds.stream_search_events")
def test_ask_raw_mode(mock_stream_events, mock_auth_cls):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_auth_cls.return_value = mock_auth

    async def fake_generator(*args, **kwargs):
        yield {"event": "ai_chunk", "data": {"delta": "Hello "}}
        yield {"event": "ai_chunk", "data": {"delta": "world!"}}
        yield {"event": "citations", "data": {"sources": []}}
        yield {"event": "done", "data": {"total_tokens": 2}}

    mock_stream_events.side_effect = fake_generator

    result = runner.invoke(app, ["ask", "Hello?", "--raw"])
    assert result.exit_code == 0
    assert "Hello world!" in result.output


@patch("valstorm_cli.search_cmds.ValstormAuth")
@patch("valstorm_cli.search_cmds.stream_search_events")
def test_vfs_ask_alias(mock_stream_events, mock_auth_cls):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_auth_cls.return_value = mock_auth

    async def fake_generator(*args, **kwargs):
        yield {"event": "ai_chunk", "data": {"delta": "VFS Answer"}}

    mock_stream_events.side_effect = fake_generator

    result = runner.invoke(app, ["vfs", "ask", "Question?", "--raw"])
    assert result.exit_code == 0
    assert "VFS Answer" in result.output


def test_render_citations_table():
    citations = [
        {
            "file_name": "contract.pdf",
            "location": "/Legal/contract.pdf",
            "score": 0.95,
            "snippet": "Clause 1",
        }
    ]
    # Should execute without error
    _render_citations_table(citations)
    _render_citations_table([])


@pytest.mark.asyncio
async def test_parse_sse_stream():
    lines = [
        "event: metadata_results",
        'data: {"count": 1}',
        "",
        "event: ai_chunk",
        'data: {"delta": "test"}',
        "",
    ]

    class FakeResponse:
        async def aiter_lines(self):
            for l in lines:
                yield l

    events = []
    async for item in _parse_sse_stream(FakeResponse()):  # type: ignore
        events.append(item)

    assert len(events) == 2
    assert events[0]["event"] == "metadata_results"
    assert events[0]["data"] == {"count": 1}
    assert events[1]["event"] == "ai_chunk"
    assert events[1]["data"] == {"delta": "test"}


@patch("valstorm_cli.auth.get_auth")
def test_vfs_reindex_requires_vault_or_all(mock_get_auth):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_auth.sandbox = None
    mock_get_auth.return_value = mock_auth

    result = runner.invoke(app, ["vfs", "reindex"])
    assert result.exit_code == 1
    assert "Must specify either --vault" in result.output


@patch("valstorm_cli.auth.get_auth")
def test_vfs_reindex_with_all(mock_get_auth):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_auth.sandbox = None
    mock_client = MagicMock()
    mock_auth.get_client.return_value = mock_client
    mock_get_auth.return_value = mock_auth

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "dispatched", "total_files_queued": 42}
    mock_client.post.return_value = mock_resp

    result = runner.invoke(app, ["vfs", "reindex", "--all", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["total_files_queued"] == 42


@patch("valstorm_cli.auth.get_auth")
def test_vfs_index_command_with_file_id(mock_get_auth):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_auth.sandbox = None
    mock_client = MagicMock()
    mock_auth.get_client.return_value = mock_client
    mock_get_auth.return_value = mock_auth

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "queued", "task_id": "celery_123", "file_id": "fil_abc"}
    mock_client.post.return_value = mock_resp

    result = runner.invoke(app, ["vfs", "index", "fil_abc", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["status"] == "queued"
    assert parsed["task_id"] == "celery_123"


@patch("valstorm_cli.auth.get_auth")
def test_vfs_index_command_with_path(mock_get_auth):
    mock_auth = MagicMock()
    mock_auth.access_token = "valid_token"
    mock_auth.sandbox = None
    mock_client = MagicMock()
    mock_auth.get_client.return_value = mock_client
    mock_get_auth.return_value = mock_auth

    # Mock resolve GET response
    mock_resolve_resp = MagicMock()
    mock_resolve_resp.status_code = 200
    mock_resolve_resp.json.return_value = {"id": "fil_resolved_123"}

    # Mock index POST response
    mock_index_resp = MagicMock()
    mock_index_resp.status_code = 200
    mock_index_resp.json.return_value = {"status": "queued", "task_id": "celery_456", "file_id": "fil_resolved_123"}

    mock_client.get.return_value = mock_resolve_resp
    mock_client.post.return_value = mock_index_resp

    result = runner.invoke(app, ["vfs", "index", "/Docs/report.pdf", "--force"])
    assert result.exit_code == 0
    assert "Indexing task dispatched for file fil_resolved_123" in result.output
