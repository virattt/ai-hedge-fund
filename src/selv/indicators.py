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
    df["rsi"] = ta.rsi(
        df["close"], length=14
    )  # RSI 14 periods 🡒 traders’ classic choice [oai_citation:7‡Stack Overflow](https://stackoverflow.com/questions/57006437/calculate-rsi-indicator-from-pandas-dataframe?utm_source=chatgpt.com)
    macd = ta.macd(
        df["close"], fast=12, slow=26, signal=9
    )  # MACD line, Signal, Hist. [oai_citation:8‡Medium](https://medium.com/%40financial_python/building-a-macd-indicator-in-python-190b2a4c1777?utm_source=chatgpt.com)
    df = pd.concat([df, macd], axis=1)
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

    # --------------------------------------------------------------------------
    def _update_rsi(self, close: float) -> float | None:
        if len(self.gain_queue) == self.rsi_period:
            # remove oldest contribution
            old_gain, old_loss = self.gain_queue[0], self.loss_queue[0]
            self.avg_gain = (
                self.avg_gain * (self.rsi_period - 1) + old_gain
            ) / self.rsi_period
            self.avg_loss = (
                self.avg_loss * (self.rsi_period - 1) + old_loss
            ) / self.rsi_period
        # add newest
        change = close - self.prev_close if hasattr(self, "prev_close") else 0
        gain = max(change, 0)
        loss = max(-change, 0)
        self.gain_queue.append(gain)
        self.loss_queue.append(loss)
        if self.avg_gain is None:  # first full window
            if len(self.gain_queue) == self.rsi_period:
                self.avg_gain = np.mean(self.gain_queue)
                self.avg_loss = np.mean(self.loss_queue)
        else:
            self.avg_gain = (
                self.avg_gain * (self.rsi_period - 1) + gain
            ) / self.rsi_period
            self.avg_loss = (
                self.avg_loss * (self.rsi_period - 1) + loss
            ) / self.rsi_period
        self.prev_close = close
        if self.avg_loss == 0 or self.avg_gain is None:
            return None
        rs = self.avg_gain / self.avg_loss
        return 100 - (100 / (1 + rs))

    # --------------------------------------------------------------------------
    def update(self, ohlcv: dict) -> dict | None:
        """
        Update indicators with the latest bar.
        `ohlcv` is a dict {'timestamp': int, 'open': float, ... , 'close': float}
        Returns a signal dict when an entry or exit action is generated.
        """
        close = ohlcv["close"]
        rsi_val = self._update_rsi(close)
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
