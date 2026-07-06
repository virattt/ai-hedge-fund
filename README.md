# AI Hedge Fund on Render

Deploy an AI-powered hedge fund on Render in one click. A team of ~19 famous-investor agents — Warren Buffett, Charlie Munger, Michael Burry, Cathie Wood, and more — analyze the tickers you choose and produce trading signals and a final portfolio decision. You get a **FastAPI backend**, a **React web UI**, and a **managed PostgreSQL database**, all wired together automatically.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Ho1yShif/ai-hedge-fund)

> [!WARNING]
> This project is for **educational and research purposes only**. It does **not** place real trades and is not investment advice. See the [Disclaimer](#disclaimer).

## Architecture

The [`render.yaml`](render.yaml) Blueprint provisions three resources, grouped under a single **`ai-hedge-fund`** Render project (a `production` environment) so they appear together in the Dashboard:

```
                 ┌─────────────────────────┐
 Browser  ─────► │  ai-hedge-fund-web       │   React/Vite static site (CDN)
                 │  (static site)           │
                 └───────────┬─────────────┘
                             │ VITE_API_URL (auto-wired)
                             ▼
                 ┌─────────────────────────┐
                 │  ai-hedge-fund-api       │   FastAPI backend (agents + backtester)
                 │  (web service, Python)   │
                 └───────────┬─────────────┘
                             │ DATABASE_URL (auto-wired)
                             ▼
                 ┌─────────────────────────┐
                 │  ai-hedge-fund-db        │   Managed PostgreSQL
                 │  (Postgres)              │
                 └─────────────────────────┘
```

| Resource | Type | Role |
|----------|------|------|
| `ai-hedge-fund-api` | Python web service | REST API that runs the agents and the backtester |
| `ai-hedge-fund-web` | Static site | React/Vite front end served over Render's CDN |
| `ai-hedge-fund-db` | PostgreSQL | Persists saved flows, runs, and API keys |

## What's pre-baked for Render

- **One Blueprint, one project.** `render.yaml` declares the backend, frontend, and database inside a single `ai-hedge-fund` project — no manual service creation, and all resources land in one Dashboard project.
- **`DATABASE_URL` is auto-wired** from the managed Postgres into the backend. You never set it by hand.
- **`VITE_API_URL` is auto-wired** from the backend's URL into the frontend build. The front end knows where the API lives with no configuration.
- **CORS is auto-wired and locked down.** `FRONTEND_URL` is injected from the frontend service's host, so the backend allows exactly that origin (plus localhost for dev) — not a blanket `*.onrender.com`.
- **SPA routing** is handled by a static-site rewrite to `index.html`.

## Prerequisites

**Required:**
- A [Render account](https://dashboard.render.com/register) (the free plan is enough to try it).
- **An LLM provider and API key** — pick one of [OpenAI](https://platform.openai.com/), [Anthropic](https://anthropic.com/), [Groq](https://groq.com/), [Google Gemini](https://ai.dev/), or [DeepSeek](https://deepseek.com/), and supply it via `LLM_PROVIDER` + `LLM_API_KEY`.

**Optional:**
- A [Financial Datasets](https://financialdatasets.ai/) API key. `AAPL`, `GOOGL`, `MSFT`, `NVDA`, and `TSLA` are free without a key; other tickers need one.

## Deploy

### Option 1: Deploy button

1. **Fork** this repository (the Blueprint deploys from your fork's default branch).
2. In your fork's README, click the **Deploy to Render** button (update the button URL to point at your fork if you renamed it).
3. When Render prompts for environment variables, set **`LLM_PROVIDER`** and **`LLM_API_KEY`** (see [Environment variables](#environment-variables)). Leave the rest blank.
4. Click **Apply**. Render builds the backend, builds the frontend, provisions Postgres, and connects them.

> On a fresh **Apply**, Render wires the two services' public URLs to each other automatically (`VITE_API_URL` and `FRONTEND_URL`) — there's no manual URL step and no post-Apply redeploy needed.

### Option 2: Manual Blueprint sync

1. **Fork** this repository.
2. In the Render Dashboard, choose **New → Blueprint**.
3. Connect your GitHub account and select your fork. Render reads `render.yaml` automatically.
4. Fill in the environment variables (below) and click **Apply**.

## Environment variables

Set these in the Render Dashboard at deploy time, or later from the app's **Settings** page. Supply **one** LLM provider and its key.

| Variable | Required? | What it's for |
|----------|-----------|---------------|
| `LLM_API_KEY` | required | API key for your LLM provider. With no `LLM_PROVIDER` set, this is treated as an OpenAI key. Keys: [OpenAI](https://platform.openai.com/), [Anthropic](https://anthropic.com/), [Groq](https://groq.com/), [Google Gemini](https://ai.dev/), [DeepSeek](https://deepseek.com/). |
| `LLM_PROVIDER` | optional | Provider for `LLM_API_KEY`, one of `OpenAI`, `Anthropic`, `Groq`, `Google`, `DeepSeek`, `OpenRouter`, `xAI`, `Kimi`, `GigaChat`. Leave blank to use OpenAI. |
| `FINANCIAL_DATASETS_API_KEY` | optional | Financial data for tickers beyond the five free ones — [financialdatasets.ai](https://financialdatasets.ai/) |
| `DATABASE_URL` | auto | Injected from the managed Postgres — **do not set manually**. |
| `VITE_API_URL` | auto | Injected into the frontend build from the backend's `RENDER_EXTERNAL_URL` (its `https://…onrender.com` URL, slug included) — **do not set manually**. |
| `FRONTEND_URL` | auto | Injected from the frontend's `RENDER_EXTERNAL_URL` and used as the CORS allow-list. Set manually only for a custom frontend domain (comma-separated origins). |

### Choosing your LLM

Set `LLM_API_KEY` to an OpenAI key and the app runs on **OpenAI `gpt-5.5`** out of the box — no `LLM_PROVIDER` needed. `LLM_PROVIDER` only supplies the credential routing; it does **not** by itself change which model runs.

- Leaving `LLM_PROVIDER` blank (or setting it to `OpenAI`) works with the default model out of the box.
- To use any other provider, set `LLM_PROVIDER` to that provider and **pick a matching-provider model in the app UI** (or pass `--provider` on the CLI). Otherwise the app keeps requesting the OpenAI default, your key won't match it, and you'll see an "OpenAI API key not found" error.

You can also set per-provider keys (e.g. `OPENAI_API_KEY`) or manage keys from the app's **Settings** page; those take precedence over `LLM_API_KEY` for their provider.

## Post-deploy setup

1. Wait for all three services to go **live** in the Dashboard (the first backend build takes a few minutes).
2. If you didn't set your LLM key at deploy time, add it now: either on the `ai-hedge-fund-api` service's **Environment** tab, or in the app's **Settings** page once it's open.
3. Open the `ai-hedge-fund-web` URL and start a run.

## Using the AI hedge fund

In the web UI you pick the tickers to analyze, choose which investor agents participate, and select the LLM model. The agents each produce a signal; a **Risk Manager** sets position limits and a **Portfolio Manager** makes the final call. You can also run a **backtester** over a historical date range.

The investor agents include:

Aswath Damodaran · Ben Graham · Bill Ackman · Cathie Wood · Charlie Munger · Michael Burry · Mohnish Pabrai · Nassim Taleb · Peter Lynch · Phil Fisher · Rakesh Jhunjhunwala · Stanley Druckenmiller · Warren Buffett — plus **Valuation**, **Sentiment**, **Fundamentals**, and **Technicals** analysts, a **Risk Manager**, and a **Portfolio Manager**.

## Cost expectations

The Blueprint uses **free** plans for all three resources so you can try it at no cost.

## Run locally

The app also runs locally (CLI and web). See [`app/README.md`](app/README.md) for the full-stack web app and the quick CLI path below:

```bash
cp .env.example .env          # add at least one LLM key
poetry install
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

Locally the backend falls back to SQLite when `DATABASE_URL` is unset, so no database setup is required for development.

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| Backend deploy fails during build | Python version mismatch — the Blueprint pins `PYTHON_VERSION=3.11.9`; keep it (deps require 3.11). |
| App loads but every run errors with an auth/key message | No LLM key set. Add one on the `ai-hedge-fund-api` **Environment** tab or in the app's **Settings**. |
| First request hangs ~30–60s | Free-tier cold start — the service is waking up. Subsequent requests are fast. |
| Runs work for some tickers but not others | Tickers outside the five free ones need `FINANCIAL_DATASETS_API_KEY`. |
| Frontend loads but the flows list spins forever / CORS errors in the network tab | The backend's `FRONTEND_URL` must equal the frontend's URL (it's the CORS allow-list). A fresh **Apply** wires this automatically, but a **code-only redeploy does not (re)create `fromService` env vars** — so if `FRONTEND_URL` is missing (e.g. it was added to `render.yaml` after the first deploy, or you renamed a service), run a **Blueprint sync** (Dashboard → your Blueprint → **Sync**), not just a redeploy. For a custom frontend domain, add it to `FRONTEND_URL` (comma-separated origins). |
| "OpenAI API key not found" with a non-OpenAI key | Your `LLM_PROVIDER` isn't OpenAI but the app is still requesting the OpenAI default — pick a matching-provider model in the app UI (or `--provider` on the CLI). |
| Data doesn't persist across restarts | You're on the free Postgres (expires after 30 days) or fell back to SQLite locally — upgrade the DB plan for durability. |

## What this template does and doesn't do

**Does:**
- Deploy a working, multi-agent AI hedge-fund web app on Render with one click.
- Provision and wire together a backend, frontend, and Postgres database.
- Let you experiment with different investor agents, LLMs, and backtests.

**Doesn't:**
- Place real trades or connect to a brokerage.
- Provide investment advice or guarantees of any kind.
- Ship a production system with auth and rate limiting — it's a demo/educational template.

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results

## License

MIT — see [LICENSE](LICENSE). Based on [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund).
