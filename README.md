# Gatent

**The web action layer for agents.** Declarative watch/extract/diff/notify modules exposed over REST, MCP, and CLI.

Status: **v0.1.0** (alpha, open-core, Apache-2.0)

## What it does

Gatent turns "watch this page/API and tell me when something changes" into a YAML file. Each module declares:

- **navigate** - where to go (HTTP API call or browser via Playwright)
- **extract** - what to pull out (CSS selectors or JSONPath)
- **transform** - cleanup (regex, coalesce, cast)
- **diff** - what counts as a change (identity fields, content fields)
- **route** - where changes go (sinks + notifiers, with severity and approval gates)

Every module is simultaneously:
- an **MCP tool** any agent can call (`gatent serve --mcp-stdio`)
- a **REST endpoint** (`POST /v1/modules/{id}/run`)
- a **CLI command** (`gatent run my-watcher`)
- a **cron job** (declarative schedule per module)

## Quickstart

```bash
pip install -e .

# Scaffold a module from a template
gatent modules init my-watcher --template hn-watcher

# Run it once
gatent run my-watcher

# Serve REST + Swagger UI
gatent serve
# -> http://127.0.0.1:8200/v1/docs

# Expose all modules as MCP tools (Claude Desktop, Cursor)
gatent serve --mcp-stdio
```

Claude Desktop config:

```json
{
  "mcpServers": {
    "gatent": { "command": "gatent", "args": ["serve", "--mcp-stdio"] }
  }
}
```

## Profiles

- **solo_local** (default): SQLite state, YAML module files, OS keychain vault. Zero cloud dependencies.
- **cloud**: Supabase state store, Notion config store, envelope-encrypted vault (AWS KMS + Postgres), Playwright browser runner. Install with `pip install -e ".[cloud]"`. Deployable to Modal via `gatent/deploy.py`.

## Reference modules

See `modules/` for ready-to-use YAML:

| Module | Use case | Auth |
|---|---|---|
| `procore-rfi-watcher` | Construction RFI monitoring | api_key |
| `rec-gov-availability` | Campsite availability alerts | none |
| `rec-gov-book` | Campsite booking (approval-gated) | session_login |
| `kdp-title-status` | Amazon KDP publishing status | session_login |
| `ntfy-approval-gate` | Human-approval primitive | none |

High-stakes modules set `mcp_exposed: false` and `requires_approval: true` - agents cannot see them, and even direct calls require a human tap on an ntfy push before the action fires.

## Security model

- Credentials never live in module YAML - only `auth_profile_id` references.
- solo_local: secrets in the OS keychain.
- cloud: envelope encryption (AES-256-GCM, per-secret DEKs, KMS-wrapped), AAD-bound to profile IDs, full audit trail.

## License

Apache-2.0. Copyright Empty-M Software LLC.
