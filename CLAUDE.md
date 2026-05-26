# Valstorm CLI — Claude Guide

Python CLI tool for developers to manage local Valstorm workspaces, sync metadata, and authenticate.

## Tech Stack

- **Framework**: Typer (Python CLI)
- **HTTP Client**: HTTPX
- **Package Manager**: uv
- **Console UI**: Rich library

## Key Files

```
cli/
  src/valstorm_cli/
    main.py    # All CLI commands (login, init, pull, push, status)
    auth.py    # Token management, refresh logic
    stubs/     # Type stubs
  pyproject.toml
```

## Commands

```bash
# Run via uv
uv run --project cli valstorm <command>

# Login (being refactored to PKCE Auth Code flow)
valstorm login

# Init workspace (creates valstorm.json, object/, schemas/ dirs)
valstorm init

# Pull remote schemas to local filesystem
valstorm pull

# Push local changes to cloud
valstorm push

# Check API health
valstorm status
```

## Authentication

Tokens stored at: `~/.valstorm/auth_{env}_{profile}.json`

- Supports multiple profiles (dev, prod, local)
- Auto-refresh token logic in `auth.py`
- MCP server reads tokens from the same location

### Current Auth Refactor: PKCE OAuth Flow

Migrating `valstorm login` from Password grant → Authorization Code + PKCE.

New flow (see `plans/dev plans/cli-oauth-auth-code-flow.md`):
1. Generate `code_verifier` + `code_challenge` (SHA-256 + base64url)
2. Generate random `state`
3. Spin up local HTTP server on `localhost:8011/callback`
4. Open browser to `https://app.valstorm.com/oauth2/login?client_id=...&code_challenge=...`
5. Capture `code` from redirect
6. Exchange `code` + `code_verifier` for tokens (no `client_secret` needed)
7. Store tokens in `~/.valstorm/auth_{env}_{profile}.json`

Benefit: Refresh tokens can last 365 days vs current 7-day limit.

## Configuration

`valstorm.json` in the workspace root:
```json
{
  "env": "dev",
  "profile": "default"
}
```

## Workspace Structure After `init`

```
<workspace>/
  valstorm.json      # Config (env, profile)
  object/            # Local object/schema definitions
  schemas/           # Schema metadata stubs
```

## MCP Integration

The CLI's auth tokens are shared with the MCP server (`apps/valstorm-mcp`). The MCP server reads `~/.valstorm/auth_{env}_{profile}.json` directly — no separate login needed.
