# Milestone 6: Telegram Bot Notifications

**Goal:** Send Telegram alerts when the hedge fund produces strong signals, notable news events, or portfolio changes — so the user stays informed without watching the terminal.

**Risk:** Low
**Dependencies:** None (can start anytime)

## Key Decisions

- Use `python-telegram-bot` library (async, well-maintained)
- Bot token via `TELEGRAM_BOT_TOKEN` env var, chat ID via `TELEGRAM_CHAT_ID`
- Pluggable notification manager in `src/notifications/` (Telegram first, easy to add Discord/Slack later)
- Notification triggers: strong agent signals (confidence > threshold), portfolio trade decisions, daily summary
- Configurable via new DB table (alert thresholds, enabled topics) + new `/notifications` API route
- Gate behind env vars — no Telegram config = notifications silently disabled

## Tasks

- [ ] Add `python-telegram-bot>=21.0` to `pyproject.toml`
- [ ] Create `src/notifications/__init__.py`
- [ ] Create `src/notifications/telegram_bot.py` with `TelegramNotifier` class
  - `send_message(text)`
  - `send_signal_alert(ticker, signal, confidence)`
  - `send_portfolio_update(trades)`
  - `send_daily_summary(portfolio_state)`
- [ ] Create `src/notifications/manager.py` with `NotificationManager`
  - Registers notifiers
  - Filters by threshold/topic
  - Dispatches to all active channels
- [ ] Create `app/backend/models/notification.py` — SQLAlchemy model for notification config
- [ ] Create `app/backend/routes/notifications.py` — CRUD for notification preferences (thresholds, topics, chat ID)
- [ ] Register notifications router in `app/backend/main.py`
- [ ] Hook notifications into `src/agents/portfolio_manager.py` — call `notification_manager.notify_portfolio_update()` after trade decisions
- [ ] Hook run-complete summary into `src/main.py` — call `notification_manager.notify_run_complete()` with summary at end of pipeline
- [ ] Write tests in `tests/test_telegram_bot.py` — mock Telegram API calls
- [ ] Write tests in `tests/test_notification_manager.py` — test filtering and dispatch logic
- [ ] Integration test: run with Telegram bot configured

## Files to Create

| File | Purpose |
|------|---------|
| `src/notifications/__init__.py` | Package init |
| `src/notifications/telegram_bot.py` | TelegramNotifier class |
| `src/notifications/manager.py` | NotificationManager (pluggable dispatcher) |
| `app/backend/models/notification.py` | SQLAlchemy model for notification config |
| `app/backend/routes/notifications.py` | CRUD API for notification preferences |
| `tests/test_telegram_bot.py` | Unit tests for TelegramNotifier |
| `tests/test_notification_manager.py` | Unit tests for NotificationManager |

## Files to Modify

| File | Change |
|------|--------|
| `pyproject.toml` | Add `python-telegram-bot>=21.0` |
| `app/backend/main.py` | Register `/notifications` router |
| `src/agents/portfolio_manager.py` | Call notification_manager after trade decisions |
| `src/main.py` | Call notification_manager at end of pipeline |

## Verification

1. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` env vars
2. Run `poetry run python src/main.py --ticker AAPL`
3. Receive Telegram message with signal summary and trade decisions
4. Without env vars set → no errors, notifications silently skipped
