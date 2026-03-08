"""Basic Black-Scholes Greeks for delta/theta/gamma validation."""

import math
from dataclasses import dataclass


@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float


def norm_cdf(x: float) -> float:
    """Cumulative distribution function of standard normal."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """PDF of standard normal."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


class GreeksCalculator:
    """
    Black-Scholes Greeks. Use for validation; live brokers provide their own Greeks.
    """

    @staticmethod
    def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
        if T <= 0 or sigma <= 0:
            return 0.0
        return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))

    @staticmethod
    def d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
        if T <= 0 or sigma <= 0:
            return 0.0
        return GreeksCalculator.d1(S, K, T, r, sigma) - sigma * math.sqrt(T)

    @staticmethod
    def call_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
        return norm_cdf(GreeksCalculator.d1(S, K, T, r, sigma))

    @staticmethod
    def put_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
        return norm_cdf(GreeksCalculator.d1(S, K, T, r, sigma)) - 1.0

    @staticmethod
    def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0.0
        d1 = GreeksCalculator.d1(S, K, T, r, sigma)
        return norm_pdf(d1) / (S * sigma * math.sqrt(T))

    @staticmethod
    def theta_approx(
        S: float, K: float, T: float, r: float, sigma: float, is_call: bool
    ) -> float:
        """Approximate theta (per day)."""
        if T <= 0:
            return 0.0
        d1 = GreeksCalculator.d1(S, K, T, r, sigma)
        d2 = GreeksCalculator.d2(S, K, T, r, sigma)
        term1 = -S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))
        if is_call:
            term2 = r * K * math.exp(-r * T) * norm_cdf(d2)
            return (term1 - term2) / 365.0
        term2 = r * K * math.exp(-r * T) * norm_cdf(-d2)
        return (term1 + term2) / 365.0

    @staticmethod
    def vega(S: float, K: float, T: float, r: float) -> float:
        """Vega per 1% move in vol."""
        if T <= 0:
            return 0.0
        d1 = GreeksCalculator.d1(S, K, T, r, 0.20)
        return S * norm_pdf(d1) * math.sqrt(T) / 100.0

    @staticmethod
    def greeks(
        S: float, K: float, T: float, r: float, sigma: float, is_call: bool
    ) -> Greeks:
        delta = (
            GreeksCalculator.call_delta(S, K, T, r, sigma)
            if is_call
            else GreeksCalculator.put_delta(S, K, T, r, sigma)
        )
        return Greeks(
            delta=delta,
            gamma=GreeksCalculator.gamma(S, K, T, r, sigma),
            theta=GreeksCalculator.theta_approx(S, K, T, r, sigma, is_call),
            vega=GreeksCalculator.vega(S, K, T, r),
        )
