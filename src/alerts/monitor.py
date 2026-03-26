"""
Options Position Monitor & Phone Alert System

Monitors your open options positions against live prices from Yahoo Finance.
Calls your phone via Twilio when a position hits a sell threshold.

Thresholds are calculated per-position:
  - Profit target: straddle/strangle value exceeds entry cost by X%
  - Stop loss: time decay kills remaining value below floor
  - Expiry warning: alerts before final-day theta crush

Usage:
  # One-shot check
  poetry run python -m src.alerts.monitor --check

  # Run continuously (checks every 60 seconds during market hours)
  poetry run python -m src.alerts.monitor --run

  # Add a new position
  poetry run python -m src.alerts.monitor --add

  # List positions
  poetry run python -m src.alerts.monitor --list

  # Test phone call
  poetry run python -m src.alerts.monitor --test-call

Env vars required (add to .env):
  TWILIO_ACCOUNT_SID=your_sid
  TWILIO_AUTH_TOKEN=your_token
  TWILIO_FROM_NUMBER=+1xxxxxxxxxx
  ALERT_PHONE_NUMBER=+1xxxxxxxxxx
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

POSITIONS_FILE = Path(__file__).parent / "positions.json"

# ── Alert thresholds ────────────────────────────────────────────────────────
DEFAULT_PROFIT_TARGET_PCT = 50    # Sell when straddle value is 50%+ above entry
DEFAULT_DOUBLE_TARGET_PCT = 100   # Urgent call when 2x your money
DEFAULT_STOP_LOSS_PCT = -70       # Alert when 70% of premium lost
DEFAULT_EXPIRY_WARNING_HOURS = 20 # Alert 20 hours before expiry


def load_positions() -> list[dict]:
    if not POSITIONS_FILE.exists():
        return []
    with open(POSITIONS_FILE) as f:
        return json.load(f).get("positions", [])


def save_positions(positions: list[dict]):
    with open(POSITIONS_FILE, "w") as f:
        json.dump({"positions": positions}, f, indent=2)


def calculate_straddle_value(ticker: str, legs: list[dict]) -> dict:
    """Calculate current value of a straddle/strangle from live prices."""
    t = yf.Ticker(ticker)
    spot = t.history(period="1d")["Close"].iloc[-1]

    total_intrinsic = 0.0
    leg_details = []

    for leg in legs:
        strike = leg["strike"]
        side = leg["side"]
        contracts = leg["contracts"]

        if side == "call":
            intrinsic = max(spot - strike, 0)
        else:
            intrinsic = max(strike - spot, 0)

        total_intrinsic += intrinsic
        leg_details.append({
            "side": side,
            "strike": strike,
            "intrinsic": round(intrinsic, 4),
            "itm": intrinsic > 0,
        })

    # Try to get actual option prices from the chain
    total_market_value = 0.0
    got_market_prices = False

    for leg in legs:
        try:
            expiry = leg["expiry"]
            chain = t.option_chain(expiry)
            if leg["side"] == "call":
                opts = chain.calls
            else:
                opts = chain.puts

            row = opts[opts["strike"] == leg["strike"]]
            if not row.empty:
                mid = (row.iloc[0]["bid"] + row.iloc[0]["ask"]) / 2
                total_market_value += mid
                got_market_prices = True
        except Exception:
            pass

    if not got_market_prices:
        total_market_value = total_intrinsic

    return {
        "spot": round(spot, 2),
        "total_intrinsic": round(total_intrinsic, 4),
        "total_market_value": round(total_market_value, 4),
        "legs": leg_details,
        "got_live_option_prices": got_market_prices,
    }


def evaluate_position(position: dict) -> dict:
    """Evaluate a position and determine if an alert should fire."""
    ticker = position["ticker"]
    legs = position["legs"]
    entry_cost = position["total_cost_per_share"]
    total_cost = position["total_cost"]
    contracts = legs[0]["contracts"]

    val = calculate_straddle_value(ticker, legs)
    current_value = val["total_market_value"]

    # P&L
    pnl_per_share = current_value - entry_cost
    pnl_pct = (pnl_per_share / entry_cost * 100) if entry_cost > 0 else 0
    pnl_total = pnl_per_share * 100 * contracts

    # Time to expiry
    expiry_str = legs[0]["expiry"]
    expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d").replace(hour=16)  # market close
    hours_to_expiry = (expiry_dt - datetime.now()).total_seconds() / 3600

    # Determine alert level
    alert = None
    alert_level = None  # "info", "warning", "urgent"

    profit_target = position.get("profit_target_pct", DEFAULT_PROFIT_TARGET_PCT)
    double_target = position.get("double_target_pct", DEFAULT_DOUBLE_TARGET_PCT)
    stop_loss = position.get("stop_loss_pct", DEFAULT_STOP_LOSS_PCT)
    expiry_warn = position.get("expiry_warning_hours", DEFAULT_EXPIRY_WARNING_HOURS)

    if pnl_pct >= double_target:
        alert = f"DOUBLED! {ticker} straddle up {pnl_pct:+.0f}% (+${pnl_total:,.0f}). SELL NOW."
        alert_level = "urgent"
    elif pnl_pct >= profit_target:
        alert = f"PROFIT TARGET: {ticker} straddle up {pnl_pct:+.0f}% (+${pnl_total:,.0f}). Consider selling."
        alert_level = "warning"
    elif pnl_pct <= stop_loss:
        alert = f"STOP LOSS: {ticker} straddle down {pnl_pct:+.0f}% (${pnl_total:,.0f}). Salvage remaining value."
        alert_level = "warning"
    elif 0 < hours_to_expiry <= expiry_warn:
        alert = f"EXPIRY WARNING: {ticker} straddle expires in {hours_to_expiry:.0f} hours. Current value ${current_value:.2f} vs entry ${entry_cost:.2f}."
        alert_level = "info"
    elif hours_to_expiry <= 0:
        alert = f"EXPIRED: {ticker} straddle has expired. Final value ${current_value:.2f}."
        alert_level = "info"

    return {
        "ticker": ticker,
        "spot": val["spot"],
        "entry_cost": entry_cost,
        "current_value": current_value,
        "pnl_pct": round(pnl_pct, 1),
        "pnl_total": round(pnl_total, 2),
        "hours_to_expiry": round(hours_to_expiry, 1),
        "legs": val["legs"],
        "got_live_option_prices": val["got_live_option_prices"],
        "alert": alert,
        "alert_level": alert_level,
    }


# ── Phone call via Twilio ───────────────────────────────────────────────────

def call_phone(message: str):
    """Place a phone call via Twilio with a spoken alert message."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    to_number = os.environ.get("ALERT_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_number, to_number]):
        print("ERROR: Missing Twilio env vars. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, ALERT_PHONE_NUMBER in .env")
        print(f"Would have called with: {message}")
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)

        # TwiML: speak the message, repeat once
        twiml = f"""<Response>
            <Say voice="alice" language="en-US">{message}</Say>
            <Pause length="2"/>
            <Say voice="alice" language="en-US">Repeating: {message}</Say>
        </Response>"""

        call = client.calls.create(
            twiml=twiml,
            to=to_number,
            from_=from_number,
        )
        print(f"  Phone call placed: {call.sid}")
        return True
    except Exception as e:
        print(f"  Phone call failed: {e}")
        return False


def send_sms(message: str):
    """Send an SMS via Twilio as a backup/complement to the call."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    to_number = os.environ.get("ALERT_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_number, to_number]):
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=message,
            to=to_number,
            from_=from_number,
        )
        print(f"  SMS sent: {msg.sid}")
        return True
    except Exception as e:
        print(f"  SMS failed: {e}")
        return False


# ── Alert deduplication ─────────────────────────────────────────────────────

ALERT_COOLDOWN_FILE = Path(__file__).parent / ".alert_cooldowns.json"
COOLDOWN_MINUTES = 30  # Don't re-alert for same position within 30 min


def should_alert(position_key: str) -> bool:
    """Check if we've already alerted for this position recently."""
    cooldowns = {}
    if ALERT_COOLDOWN_FILE.exists():
        with open(ALERT_COOLDOWN_FILE) as f:
            cooldowns = json.load(f)

    last_alert = cooldowns.get(position_key)
    if last_alert:
        last_dt = datetime.fromisoformat(last_alert)
        if datetime.now() - last_dt < timedelta(minutes=COOLDOWN_MINUTES):
            return False

    cooldowns[position_key] = datetime.now().isoformat()
    with open(ALERT_COOLDOWN_FILE, "w") as f:
        json.dump(cooldowns, f, indent=2)
    return True


# ── Market hours check ──────────────────────────────────────────────────────

def is_market_hours() -> bool:
    """Check if US equity markets are open (rough check, no holiday calendar)."""
    now = datetime.now()
    # Weekday and between 9:30 AM - 4:00 PM ET (adjust if not in ET)
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0)
    market_close = now.replace(hour=16, minute=0, second=0)
    return market_open <= now <= market_close


# ── CLI ─────────────────────────────────────────────────────────────────────

def check_all():
    """Check all positions once and print status."""
    positions = load_positions()
    if not positions:
        print("No positions found. Use --add to add one.")
        return

    print(f"\n{'=' * 70}")
    print(f"  OPTIONS POSITION MONITOR — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 70}\n")

    for pos in positions:
        try:
            result = evaluate_position(pos)
            ticker = result["ticker"]
            price_source = "LIVE" if result["got_live_option_prices"] else "INTRINSIC"

            print(f"  {ticker} {'straddle' if pos['type'] == 'straddle' else 'strangle'}")
            print(f"    Spot: ${result['spot']}")
            for leg in result["legs"]:
                itm = "ITM" if leg["itm"] else "OTM"
                print(f"    {leg['side'].upper()} ${leg['strike']}: intrinsic ${leg['intrinsic']:.2f} ({itm})")
            print(f"    Entry: ${result['entry_cost']:.2f} | Current: ${result['current_value']:.2f} [{price_source}]")
            print(f"    P&L: {result['pnl_pct']:+.1f}% (${result['pnl_total']:+,.0f})")
            print(f"    Expires in: {result['hours_to_expiry']:.0f} hours")

            if result["alert"]:
                level = result["alert_level"].upper()
                print(f"    *** {level}: {result['alert']} ***")

                pos_key = f"{ticker}_{pos['legs'][0]['expiry']}_{pos['legs'][0]['strike']}"
                if should_alert(pos_key):
                    if result["alert_level"] == "urgent":
                        call_phone(result["alert"])
                        send_sms(result["alert"])
                    elif result["alert_level"] == "warning":
                        call_phone(result["alert"])
                    else:
                        send_sms(result["alert"])
                else:
                    print(f"    (alert suppressed — cooldown active)")
            else:
                print(f"    Status: OK — no alert triggered")

            print()
        except Exception as e:
            print(f"  {pos['ticker']}: ERROR — {e}\n")


def run_continuous(interval_seconds: int = 60):
    """Run the monitor continuously."""
    print(f"Starting continuous monitor (checking every {interval_seconds}s during market hours)")
    print(f"Press Ctrl+C to stop\n")

    while True:
        try:
            if is_market_hours():
                check_all()
            else:
                now = datetime.now()
                print(f"  [{now.strftime('%H:%M')}] Market closed. Waiting...")

            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break


def add_position_interactive():
    """Interactive CLI to add a new position."""
    print("\n=== Add New Options Position ===\n")

    ticker = input("Ticker (e.g. UNG): ").strip().upper()
    pos_type = input("Type (straddle/strangle): ").strip().lower()

    legs = []
    if pos_type == "straddle":
        strike = float(input("Strike price: "))
        expiry = input("Expiry (YYYY-MM-DD): ").strip()
        contracts = int(input("Contracts per leg: "))
        call_price = float(input("Call entry price (per share): "))
        put_price = float(input("Put entry price (per share): "))
        legs = [
            {"side": "call", "strike": strike, "expiry": expiry, "contracts": contracts, "entry_price": call_price},
            {"side": "put", "strike": strike, "expiry": expiry, "contracts": contracts, "entry_price": put_price},
        ]
        total_per_share = call_price + put_price
    elif pos_type == "strangle":
        put_strike = float(input("Put strike: "))
        call_strike = float(input("Call strike: "))
        expiry = input("Expiry (YYYY-MM-DD): ").strip()
        contracts = int(input("Contracts per leg: "))
        call_price = float(input("Call entry price (per share): "))
        put_price = float(input("Put entry price (per share): "))
        legs = [
            {"side": "call", "strike": call_strike, "expiry": expiry, "contracts": contracts, "entry_price": call_price},
            {"side": "put", "strike": put_strike, "expiry": expiry, "contracts": contracts, "entry_price": put_price},
        ]
        total_per_share = call_price + put_price
    else:
        print("Unknown type. Use 'straddle' or 'strangle'.")
        return

    total_cost = total_per_share * 100 * contracts

    # Custom thresholds
    profit_target = input(f"Profit target % (default {DEFAULT_PROFIT_TARGET_PCT}): ").strip()
    profit_target = int(profit_target) if profit_target else DEFAULT_PROFIT_TARGET_PCT
    stop_loss = input(f"Stop loss % (default {DEFAULT_STOP_LOSS_PCT}): ").strip()
    stop_loss = int(stop_loss) if stop_loss else DEFAULT_STOP_LOSS_PCT

    notes = input("Notes (optional): ").strip()

    position = {
        "ticker": ticker,
        "type": pos_type,
        "legs": legs,
        "total_cost_per_share": total_per_share,
        "total_cost": total_cost,
        "entered": datetime.now().strftime("%Y-%m-%d"),
        "profit_target_pct": profit_target,
        "stop_loss_pct": stop_loss,
        "notes": notes,
    }

    positions = load_positions()
    positions.append(position)
    save_positions(positions)

    print(f"\nAdded: {ticker} {pos_type} — {contracts} contracts, ${total_cost:,.0f} total")
    print(f"Profit target: +{profit_target}% | Stop loss: {stop_loss}%")


def list_positions():
    """Print all tracked positions."""
    positions = load_positions()
    if not positions:
        print("No positions tracked. Use --add to add one.")
        return

    print(f"\n{'=' * 60}")
    print(f"  TRACKED POSITIONS")
    print(f"{'=' * 60}\n")

    for i, pos in enumerate(positions):
        legs_str = " + ".join(
            f"{l['side'].upper()} ${l['strike']} x{l['contracts']}"
            for l in pos["legs"]
        )
        expiry = pos["legs"][0]["expiry"]
        hours = (datetime.strptime(expiry, "%Y-%m-%d").replace(hour=16) - datetime.now()).total_seconds() / 3600

        print(f"  [{i}] {pos['ticker']} {pos['type'].upper()}")
        print(f"      {legs_str}")
        print(f"      Expiry: {expiry} ({hours:.0f}h) | Entry: ${pos['total_cost_per_share']:.2f}/sh | Total: ${pos['total_cost']:,.0f}")
        profit_t = pos.get('profit_target_pct', DEFAULT_PROFIT_TARGET_PCT)
        stop_l = pos.get('stop_loss_pct', DEFAULT_STOP_LOSS_PCT)
        print(f"      Alerts: profit +{profit_t}% | stop {stop_l}%")
        if pos.get("notes"):
            print(f"      Notes: {pos['notes']}")
        print()


def test_call():
    """Place a test phone call."""
    print("Placing test call...")
    call_phone("This is a test alert from your options monitor. If you hear this, the system is working correctly.")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--check" in args:
        check_all()
    elif "--run" in args:
        interval = 60
        for a in args:
            if a.startswith("--interval="):
                interval = int(a.split("=")[1])
        run_continuous(interval)
    elif "--add" in args:
        add_position_interactive()
    elif "--list" in args:
        list_positions()
    elif "--test-call" in args:
        test_call()
    else:
        print(__doc__)
