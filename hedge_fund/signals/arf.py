"""ARF (AI Relevance Factor) alpha model.

Forms point-in-time investment views based on Jensen Huang's 5-layer AI exposure (E-score),
valuation stretch (V-score), reverse-DCF implied growth gap, and the Froth Flag.
Connects directly to ARF's DuckDB snapshots (data/arf.db).
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

from hedge_fund.data.protocol import DataClient
from hedge_fund.models import Signal
from hedge_fund.signals.base import QuantModel

logger = logging.getLogger(__name__)

# Default location for the ARF DuckDB database
DEFAULT_ARF_DB_PATH = Path("/Users/sheng/Developer/ARF/data/arf.db")


class ARFModel(QuantModel):
    """Alpha model powered by the AI Relevance Factor (ARF) framework.

    Evaluates AI ecosystem stocks across:
    - E-score: 5-layer AI stack exposure (GPU/Compute, Interconnect, Data Center, etc.)
    - V-score: Multi-factor valuation stretch (Reverse-DCF, PEG, EV/S 5yr percentile, ROE)
    - Froth Flag: D1 valuation bubble with ROE < Cost of Equity and P/S > 25
    - Implied Growth Gap: Reverse-DCF implied growth vs. Wall Street consensus CAGR

    Conviction formulation:
    - Froth Flag -> Hard -1.0 short conviction (maximum bubble hazard).
    - Fundamental L/S Tilt -> (E_score - V_score) / 100 clamped into [-1.0, +1.0],
      boosted for high-ROE compounders and penalised for cash-burning multiples.
    """

    investment_approach = "long_short"

    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        snapshots_df: pd.DataFrame | None = None,
        froth_conviction: float = -1.0,
        quality_roe_threshold: float = 0.20,
        quality_bonus: float = 0.15,
        speculative_penalty: float = 0.20,
    ) -> None:
        self._froth_conviction = froth_conviction
        self._quality_roe_threshold = quality_roe_threshold
        self._quality_bonus = quality_bonus
        self._speculative_penalty = speculative_penalty

        if snapshots_df is not None:
            self._df = snapshots_df.copy()
        else:
            path = Path(db_path) if db_path is not None else DEFAULT_ARF_DB_PATH
            self._df = self._load_from_db(path)

        if not self._df.empty:
            self._df["as_of_date"] = pd.to_datetime(self._df["as_of_date"])

    @property
    def name(self) -> str:
        return "arf"

    def predict(self, ticker: str, date: str, data_client: DataClient) -> Signal:
        """Form a point-in-time view on *ticker* as of *date* using ARF metrics."""
        if self._df.empty:
            return self._abstain(ticker, date, "No ARF snapshot data loaded")

        ticker_clean = ticker.strip().upper()
        as_of = pd.to_datetime(date)

        # Strict point-in-time: only consider snapshots on or before `date`
        matches = self._df[
            (self._df["ticker"] == ticker_clean) & (self._df["as_of_date"] <= as_of)
        ].sort_values("as_of_date", ascending=False)

        if matches.empty:
            return self._abstain(
                ticker,
                date,
                f"{ticker_clean} not found in ARF universe on or before {date}",
            )

        row = matches.iloc[0]
        snapshot_date = row["as_of_date"].strftime("%Y-%m-%d")

        arf_score = self._safe_float(row.get("arf"), 50.0)
        decile = int(self._safe_float(row.get("decile"), 5))
        e_score = self._safe_float(row.get("e_score"), 50.0)
        v_score = self._safe_float(row.get("v_score"), 50.0)
        froth_flag = bool(row.get("froth_flag", False))
        roe = self._safe_float(row.get("roe"), 0.0)
        ps_ratio = self._safe_float(row.get("ps_ratio"), 0.0)
        growth_gap = row.get("implied_growth_gap")
        growth_gap_val = self._safe_float(growth_gap, 0.0) if pd.notna(growth_gap) else None

        # Froth Flag takes absolute precedence: speculative bubble warning
        if froth_flag:
            value = self._froth_conviction
            reasoning = (
                f"ARF Froth Warning: D{decile} valuation bubble (V={v_score:.0f}, P/S={ps_ratio:.1f}) "
                f"with ROE={roe:.1%} below Cost of Equity. High multiple contraction risk."
            )
        else:
            # Base view: AI Exposure vs Valuation Stretch
            raw_conviction = (e_score - v_score) / 100.0

            # Quality compounder adjustment
            if roe >= self._quality_roe_threshold and e_score >= 50.0 and v_score <= 50.0:
                raw_conviction += self._quality_bonus
            # Cash-burning speculative stretch penalty
            elif roe < 0.0 and v_score >= 70.0:
                raw_conviction -= self._speculative_penalty

            value = self._normalize_to_signal(raw_conviction)

            bias = "Bullish" if value > 0.15 else ("Bearish" if value < -0.15 else "Neutral")
            gap_str = f", Growth Gap={growth_gap_val:+.1%}" if growth_gap_val is not None else ""
            reasoning = (
                f"ARF {bias} (D{decile}, Score={arf_score:.1f}): Exposure E={e_score:.0f}, "
                f"Stretch V={v_score:.0f}, ROE={roe:.1%}{gap_str} (as of {snapshot_date})."
            )

        components = {
            "arf": round(arf_score, 2),
            "decile": float(decile),
            "e_score": round(e_score, 2),
            "v_score": round(v_score, 2),
            "froth_flag": 1.0 if froth_flag else 0.0,
            "roe": round(roe, 4),
        }
        if growth_gap_val is not None:
            components["implied_growth_gap"] = round(growth_gap_val, 4)

        return Signal(
            model_name=self.name,
            ticker=ticker_clean,
            date=date,
            value=round(value, 2),
            reasoning=reasoning,
            components=components,
            metadata={
                "snapshot_date": snapshot_date,
                "leg": str(row.get("leg", "")),
                "froth_flag": froth_flag,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _abstain(self, ticker: str, date: str, reason: str) -> Signal:
        return Signal(
            model_name=self.name,
            ticker=ticker.strip().upper(),
            date=date,
            value=0.0,
            reasoning=reason,
            metadata={"abstained": True},
        )

    @staticmethod
    def _load_from_db(path: Path) -> pd.DataFrame:
        """Load snapshots table from DuckDB with read_only=True."""
        if not path.exists():
            logger.warning("ARF DuckDB file not found at %s", path)
            return pd.DataFrame()
        try:
            con = duckdb.connect(str(path), read_only=True)
            cols = [
                "ticker",
                "as_of_date",
                "leg",
                "arf",
                "decile",
                "froth_flag",
                "e_score",
                "v_score",
                "implied_growth_gap",
                "roe",
                "ps_ratio",
            ]
            query = f"SELECT {', '.join(cols)} FROM snapshots"
            df = con.execute(query).df()
            con.close()
            return df
        except Exception as exc:
            logger.error("Failed to load snapshots from %s: %s", path, exc)
            return pd.DataFrame()
