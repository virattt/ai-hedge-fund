"""v2 portfolio construction — blend analyst views into target weights.

Later: mean-variance optimization, Black-Litterman, risk parity.
"""

from hedge_fund.portfolio.construction import BlendResult, blend_signals

__all__ = ["BlendResult", "blend_signals"]
