# Strategist — Quickstart

A local AI hedge-fund dashboard. Type tickers → get a full institutional-grade report
(snapshot + technicals + fundamentals + AI investor council + price targets +
backtest + journal). All your data lives on your disk at `~/.strategist/`.

## Three ways to run

### 1. One-time launch (manual)

```powershell
poetry run snapshot-ui
```

Opens http://127.0.0.1:8765/ in your browser. Console stays open until you close it.

### 2. Auto-start on Windows login (recommended)

Install once:

```powershell
scripts\install-autostart.bat
```

That drops a shortcut into your Windows Startup folder. From the next login onwards,
Strategist boots automatically and silently — open your browser to
http://127.0.0.1:8765/ any time and it's there.

The server logs to `%USERPROFILE%\.strategist\logs\strategist.log`. Verify it's up:

```powershell
curl http://127.0.0.1:8765/healthz
```

You can also start it manually without rebooting:

```powershell
scripts\strategist-start.bat --open
```

Stop it:

```powershell
scripts\strategist-stop.bat
```

Uninstall autostart:

```powershell
scripts\uninstall-autostart.bat
```

### 3. Foreground (debug mode)

```powershell
scripts\strategist-start.bat --foreground
```

Stays in the console with full output. Use when you want to see what the server is doing.

## What the platform does for you in the background

Once running, Strategist's background refresher (an internal thread, no extra process) keeps your watchlist tickers warm:

- **Every 6 hours**, it fetches a fresh snapshot for every ticker in your watchlists and saved analyses.
- When you open the dashboard, every page you've touched recently loads **instantly** because the data is already in memory.
- If **auto-save** is enabled in `/settings`, each ticker view also auto-persists once per day — your journal builds itself.
- If **auto-run AI council** is enabled in `/settings`, every detail page kicks off the 14-analyst LangGraph in the background and refreshes the page when it's done. You never manually click "Run deep analysis."

Disable the refresher entirely by setting `STRATEGIST_NO_REFRESHER=1` in your environment.

## Where your data lives

```
~/.strategist/
├── settings.json          # Your preferences (auto-save, auto-council, default tags)
├── watchlists.json        # Every watchlist you create
├── saved/
│   ├── NVDA/
│   │   ├── 2026-05-20_08-00-00.json
│   │   └── ...one file per saved analysis
│   └── ...
└── logs/
    └── strategist.log     # Server output when running in background mode
```

Want to back this up or sync across machines? `git init ~/.strategist/` and commit.

## Sleep, wake up, open the browser

That's the whole loop. The server runs in the background, the refresher keeps data fresh, your saved analyses persist forever, the AI council attaches automatically if enabled.

If you ever shut your computer down for a week and come back: log in → the autostart shortcut launches Strategist → 30 seconds later all your watchlist tickers are pre-warmed → open http://127.0.0.1:8765/ → everything's there.
