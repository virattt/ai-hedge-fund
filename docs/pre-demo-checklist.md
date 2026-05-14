# Earnings Reaction Playbook — Pre-Demo Checklist

**Run this before every booked client session.** Two minutes if everything is healthy, fifteen if something needs fixing. The goal is "zero surprises during the call."

If you can't complete this checklist 10 minutes before the call, switch to the recording-first plan in [`docs/sales-demo.md`](sales-demo.md#fallback-when-the-live-demo-fails).

---

## 1. Environment (30 seconds)

```bash
cd ~/Repo/apps/ai-hedge-fund
git status                            # Working tree should be clean or stash any WIP.
git log --oneline -3                  # Confirm you are on a known-good commit.
.venv/bin/python --version            # Should be 3.13.x.
make typecheck                        # Should exit 0.
```

If any of the above fails, **stop**. Don't demo from an unknown state.

---

## 2. Workflow smoke test (60 seconds)

```bash
uv run pytest tests/workflows -q
```

Expect 21 passed in under 2 seconds. If anything fails, **stop** — the playbook itself is broken.

---

## 3. Live LLM connectivity (30 seconds)

Hit each model provider you intend to use in the demo. The cheapest call is enough; you only need to know the credential isn't expired.

```bash
# Anthropic
.venv/bin/python -c "from anthropic import Anthropic; r = Anthropic().messages.create(model='claude-3-5-haiku-latest', max_tokens=8, messages=[{'role':'user','content':'ping'}]); print(r.content[0].text)"

# OpenAI (if used as fallback)
.venv/bin/python -c "import openai; print(openai.OpenAI().chat.completions.create(model='gpt-4o-mini', max_tokens=8, messages=[{'role':'user','content':'ping'}]).choices[0].message.content)"
```

If a provider is down or your key is rotated, **switch the demo model in the UI before the call** rather than discovering it live.

---

## 4. Checkpoint store (30 seconds)

The live demo uses a SQLite checkpoint store so the crash-recovery moment works.

```bash
# Confirm the demo DB path exists, is writable, and is empty (or contains only the previous session you've already scrubbed).
ls -la data/earnings_reaction.db 2>/dev/null || echo "Demo DB will be created on first invoke."
```

If you ran a demo today and forgot to scrub the prospect's data:

```bash
# Manual scrub — delete the DB. SqliteSaver re-creates it on next run.
rm -f data/earnings_reaction.db
echo "$(date -u +%FT%TZ) | manual_scrub | reason: pre-demo reset" >> data/scrub-audit.log
```

---

## 5. Prospect corpus swap-in (optional — 10 minutes for legal/finance prospects)

If the discovery call surfaced documents the prospect wants to see in the demo (a 10-K, a policy file, internal memos), swap them in now. The Earnings Reaction Playbook itself runs against market data — corpus swap-in matters more for the Production RAG capability (Phase 3), but the principle is the same.

Quick swap-in procedure for the demo run-context:

1. Drop prospect files into `data/demo-context/`.
2. Note the absolute paths in the run config.
3. Tag the run with the prospect alias (`prospect: acme-corp`) for audit-log attribution.
4. Confirm files are readable by the server process: `.venv/bin/python -c "from pathlib import Path; print([p.name for p in Path('data/demo-context').glob('*')])"`.

If you don't have 10 minutes, run the demo with the default ticker (rehearsed) and offer to do a follow-up session on the prospect's own data within 48 hours.

---

## 6. Streaming UI sanity (30 seconds)

```bash
# Backend
make dev                              # Or: uv run uvicorn server.main:app --reload --port 8000

# In a separate terminal — frontend
cd app && ./run.sh                    # Vite dev server on :5173
```

Open the demo URL in the browser **you'll share-screen during the call**. Confirm:

- Page loads in <1 second.
- The compose / run button is visible.
- Dark mode (if you'll demo in dark mode) renders correctly.
- Browser zoom is at 100% — not 80% from the last all-day coding session.

---

## 7. Backup paths visible (30 seconds)

- Fallback recording open in a hidden tab: `assets/demos/earnings-reaction-playbook.mp4`.
- One-pager PDF ready to attach in the post-call email.
- Pre-typed Slack/Discord message to your operations channel if the live demo bombs and you need to acknowledge it gracefully ("running into a network issue, switching to recording — back to live next session").

---

## 8. Mental check (10 seconds)

Read the opening lines from [`docs/sales-demo.md`](sales-demo.md#opening-60-seconds) out loud once. If they don't roll off the tongue, you'll stumble live.

---

## Time budget summary

| Step | Expected | If broken |
|---|---|---|
| 1. Environment | 30s | 5 min — fix uncommitted state |
| 2. Workflow smoke test | 60s | Don't demo. Tests must pass. |
| 3. LLM connectivity | 30s | 5 min — rotate credentials |
| 4. Checkpoint store | 30s | 2 min — rm + re-init |
| 5. Corpus swap-in (optional) | 10 min | Skip; use default ticker |
| 6. Streaming UI | 30s | 5 min — restart servers |
| 7. Backups visible | 30s | 1 min |
| 8. Mental check | 10s | 1 min — re-read script |

**Total green-path: 4 minutes.** Block out 15 in your calendar before each demo.

---

## Post-demo (within 1 hour of call end)

1. **Stop dev servers.** `Ctrl+C` both.
2. **Scrub prospect data if any was loaded.** See step 4 above.
3. **Log the demo in the demo-ops journal:** prospect alias, what was shown, what worked, what didn't.
4. **If the live demo failed**, file a 5-line incident note even if you recovered. Two failures of the same kind = the system isn't reliable enough; switch to recording-first.

---

## Monthly maintenance (calendar reminder, 30 minutes)

- Confirm `data/scrub-audit.log` shows entries for every demo run in the period.
- Verify fallback recording is still under 5 minutes and reflects the current UI.
- Re-time the full sales-demo script — must finish in 8 minutes.
- Bump LLM model strings if vendors deprecated anything.
- Re-run `uv sync` and confirm `tests/workflows` still passes.
