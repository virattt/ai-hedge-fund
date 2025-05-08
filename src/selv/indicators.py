import pandas as pd
import pandas_ta as ta
from collections import deque
import numpy as np


# ---------- Historical (vectorised) ----------
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds RSI‑14 and MACD(12,26,9) columns to an OHLCV DataFrame.
    Assumes 'close' price exists.
    """
    df = df.copy()
    # RSI calculation (uses RMA, equivalent to EMA with adjust=False and alpha=1/length)
    # RSI-14 is standard.
    df["rsi"] = ta.rsi(
        df["close"], length=14
    )  # RSI 14 periods 🡒 traders’ classic choice [oai_citation:7‡Stack Overflow](https://stackoverflow.com/questions/57006437/calculate-rsi-indicator-from-pandas-dataframe?utm_source=chatgpt.com)

    # MACD calculation
    # Use pandas_ta.macd directly, ensuring adjust=False is passed to its internal EMA calls.
    # This makes it consistent with RollingEMA which behaves like adjust=False.
    # Standard MACD periods: fast=12, slow=26, signal=9.
    fast_period = 12
    slow_period = 26
    signal_period = 9

    macd_df = ta.macd(
        df["close"],
        fast=fast_period,
        slow=slow_period,
        signal=signal_period,
        adjust=False,  # Critical for consistency with RollingEMA
    )
    # pandas-ta.macd returns a DataFrame with columns like 'MACD_12_26_9',
    # 'MACDh_12_26_9' (histogram), and 'MACDs_12_26_9' (signal line).

    df = pd.concat([df, macd_df], axis=1)
    # MACD line, Signal, Hist. [oai_citation:8‡Medium](https://medium.com/%40financial_python/building-a-macd-indicator-in-python-190b2a4c1777?utm_source=chatgpt.com)
    return df


# ---------- Streaming (incremental) ----------
class RollingEMA:
    """Keeps an EMA updated in O(1) time."""

    def __init__(self, span: int):
        self.alpha = 2 / (span + 1)
        self.value = None

    def update(self, price: float) -> float:
        self.value = (
            price
            if self.value is None
            else self.value + self.alpha * (price - self.value)
        )
        return self.value


class StrategyState:
    """
    Maintains running RSI‑14 and MACD(12,26,9) to evaluate signals on each new bar.
    Suitable for websocket / polling feeds.
    """

    def __init__(self, rsi_period=14, macd_fast=12, macd_slow=26, macd_signal=9):
        self.rsi_period = rsi_period
        self.gain_queue, self.loss_queue = (
            deque(maxlen=rsi_period),
            deque(maxlen=rsi_period),
        )
        self.avg_gain = self.avg_loss = None
        self.macd_fast = RollingEMA(macd_fast)
        self.macd_slow = RollingEMA(macd_slow)
        self.signal_ema = RollingEMA(macd_signal)
        self.last_macd = self.last_signal = None
        self.position = 0  # +1 long, –1 short, 0 flat
        self.entry_price = None
        self.prev_close: float | None = None  # Initialize prev_close
        self.last_rsi: float | None = None  # To store the latest RSI value

    # --------------------------------------------------------------------------
    def _update_rsi(self, close: float) -> float | None:
        if self.prev_close is None:
            self.prev_close = close
            return None  # Not enough data for a change yet

        change = close - self.prev_close
        gain = max(change, 0)
        loss = max(-change, 0)

        self.gain_queue.append(gain)
        self.loss_queue.append(loss)

        current_period_gain = gain
        current_period_loss = loss

        if len(self.gain_queue) < self.rsi_period:  # Not enough periods for initial SMA
            self.prev_close = close  # Update prev_close for next iteration
            return None

        # From here, len(self.gain_queue) == self.rsi_period as deque is maxlen
        if self.avg_gain is None or self.avg_loss is None:  # Initialize with SMA
            self.avg_gain = np.mean(
                list(self.gain_queue)
            )  # Ensure list for np.mean with deque
            self.avg_loss = np.mean(list(self.loss_queue))
        else:  # Update with Wilder's smoothing
            self.avg_gain = (
                self.avg_gain * (self.rsi_period - 1) + current_period_gain
            ) / self.rsi_period
            self.avg_loss = (
                self.avg_loss * (self.rsi_period - 1) + current_period_loss
            ) / self.rsi_period

        self.prev_close = close  # Update prev_close for the *next* call

        if self.avg_gain is None:  # Should be populated by now
            return None

        if self.avg_loss == 0:
            # If avg_loss is 0: RSI is 100 if avg_gain > 0 (all up moves).
            # If avg_gain is also 0 (no price changes), RSI is conventionally 50.
            return 100.0 if self.avg_gain > 0 else 50.0

        rs = self.avg_gain / self.avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    # --------------------------------------------------------------------------
    def update(self, ohlcv: dict) -> dict | None:
        """
        Update indicators with the latest bar.
        `ohlcv` is a dict {'timestamp': int, 'open': float, ... , 'close': float}
        Returns a signal dict when an entry or exit action is generated.
        """
        close = ohlcv["close"]
        rsi_val = self._update_rsi(close)
        self.last_rsi = rsi_val  # Store the computed RSI

        fast = self.macd_fast.update(close)
        slow = self.macd_slow.update(close)
        if fast is None or slow is None:
            return None
        macd_line = fast - slow
        signal_line = self.signal_ema.update(macd_line)
        if signal_line is None:
            return None
        # Check crossovers
        action = None
        if self.position == 0:  # flat
            if (
                macd_line > signal_line and rsi_val and rsi_val > 55
            ):  # long entry [oai_citation:9‡algobulls.github.io](https://algobulls.github.io/pyalgotrading/strategies/rsi_macd_crossover/?utm_source=chatgpt.com)
                action = "LONG"
                self.position, self.entry_price = 1, close
            elif macd_line < signal_line and rsi_val and rsi_val < 45:  # short entry
                action = "SHORT"
                self.position, self.entry_price = -1, close
        else:  # in‑position
            move = (close - self.entry_price) / self.entry_price
            if self.position == 1:  # long
                if move >= 0.02 or move <= -0.01:
                    action = "EXIT"
                    self.position = 0
            else:  # short
                if move <= -0.02 or move >= 0.01:
                    action = "EXIT"
                    self.position = 0
        self.last_macd, self.last_signal = macd_line, signal_line
        if action:
            return {"timestamp": ohlcv["timestamp"], "price": close, "signal": action}
        return None
