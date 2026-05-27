# ChatGPT Subscription LLM Provider

Open Hedge can use a **ChatGPT Plus or Pro subscription** (Codex backend) instead of a bring-your-own-key (BYOK) OpenAI API key.

## Auth contract

| Item | Value |
| --- | --- |
| OAuth authorize URL | `https://auth.openai.com/oauth/authorize` |
| OAuth token URL | `https://auth.openai.com/oauth/token` |
| Client ID | `app_EMoamEEZ73f0CkXaXp7hrann` (Codex CLI client) |
| Flow | OAuth 2.0 PKCE (`S256`) |
| Redirect URIs | `http://localhost:1455/auth/callback`, `http://localhost:1457/auth/callback` |
| Scopes | `openid profile email offline_access api.connectors.read api.connectors.invoke` |
| Extra authorize params | `codex_cli_simplified_flow=true`, `id_token_add_organizations=true`, `originator=open-hedge` |

After sign-in, access and refresh tokens are stored in the OS keychain when available, with a file fallback at `~/.open-hedge/codex-auth.json`.

Tokens refresh automatically with a **5-minute expiry buffer**. Fatal refresh errors (HTTP 400/401/403) clear stored credentials.

## Inference contract

| Item | Value |
| --- | --- |
| Endpoint | `POST https://chatgpt.com/backend-api/codex/responses` |
| Auth header | `Authorization: Bearer <access_token>` |
| Required headers | `originator: open-hedge`, `OpenAI-Beta: responses=experimental` |
| Account header | `ChatGPT-Account-Id` from JWT `chatgpt_account_id` (when present) |
| Body | `stream: true` (required by Codex backend), `store: false`, system prompt in `instructions`, user content in `input`, JSON mode via `text.format.type: json_object` |
| Response | SSE (`text/event-stream`); text assembled from `response.output_text.delta` events, with `response.completed` as fallback |

The `/responses/compact` endpoint is for conversation compaction only and rejects parameters such as `store`. Inference uses `/responses`, matching Zed's ChatGPT Subscription provider.

## Supported models

- `gpt-5.5`
- `gpt-5.4`
- `gpt-5.4-mini` (default when no model is specified)
- `gpt-5.3-codex`
- `gpt-5.2`

Model availability may vary by subscription tier; the Codex backend rejects unsupported models per account.

## Provider resolution

1. Explicit `ChatGPT Subscription` provider when signed in
2. Auto-select subscription when **no valid BYOK LLM keys** are configured and credentials exist
3. Otherwise fall back to env-based BYOK providers (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, etc.)

BYOK OpenAI and ChatGPT Subscription are separate paths: subscription uses OAuth tokens and the Codex backend, not `OPENAI_API_KEY`.

## CLI

```bash
cargo run --bin backtester -- chatgpt login
cargo run --bin backtester -- chatgpt status
cargo run --bin backtester -- chatgpt logout
```

The same `chatgpt` subcommands work on the `ai-hedge-fund` binary.

## Web API

`GET /language-models/chatgpt-subscription/status` returns:

```json
{ "authenticated": true, "email": "user@example.com" }
```

Login must be performed via CLI (browser OAuth loopback); the web UI exposes status only.
