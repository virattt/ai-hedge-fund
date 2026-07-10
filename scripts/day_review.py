"""One-off: dump today's Alpaca paper-account activity for post-day review."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from alpaca.trading.client import TradingClient  # noqa: E402
from alpaca.trading.enums import QueryOrderStatus  # noqa: E402
from alpaca.trading.requests import GetOrdersRequest  # noqa: E402

from integrations.alpaca.config import load_alpaca_config  # noqa: E402


def main() -> None:
    cfg = load_alpaca_config()
    client = TradingClient(api_key=cfg.api_key, secret_key=cfg.secret_key, paper=cfg.paper)

    account = client.get_account()
    out: dict = {
        "account": {
            "equity": float(account.equity),
            "last_equity": float(account.last_equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
        }
    }

    day_start = datetime(2026, 7, 8, tzinfo=timezone.utc)
    orders = client.get_orders(
        GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500, after=day_start)
    )
    out["orders"] = [
        {
            "symbol": o.symbol,
            "side": str(o.side),
            "qty": float(o.qty) if o.qty else None,
            "filled_qty": float(o.filled_qty) if o.filled_qty else 0.0,
            "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
            "status": str(o.status),
            "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
            "filled_at": o.filled_at.isoformat() if o.filled_at else None,
        }
        for o in orders
    ]

    positions = client.get_all_positions()
    out["positions"] = [
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "side": str(p.side),
            "avg_entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price) if p.current_price else None,
            "market_value": float(p.market_value) if p.market_value else None,
            "unrealized_pl": float(p.unrealized_pl) if p.unrealized_pl else None,
            "unrealized_plpc": float(p.unrealized_plpc) if p.unrealized_plpc else None,
        }
        for p in positions
    ]

    with open("data/day_review_20260710.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("written", file=sys.stderr)


if __name__ == "__main__":
    main()
