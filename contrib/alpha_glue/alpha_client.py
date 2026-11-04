"""A DataClient for virattt/ai-hedge-fund built on free and Alpha Vantage sources.

aihf's own client needs a Financial Datasets key, or a crypto wallet that pays per call.
This one needs neither: prices from Yahoo, fundamentals, insider trades and company facts
from SEC EDGAR as filed, and news and earnings reports (with the estimates) from Alpha
Vantage. It follows aihf's contract: only what was public by ``end_date``, and a failed
request raises instead of returning an empty list.

Run it inside aihf's own environment. It only imports ``hedge_fund`` models, never
TradingAgents, so the two stay separate.

Not provided: minute bars, sector or industry text beyond the SEC's SIC description, and
the metrics that need data these sources lack (inventory turnover, interest coverage,
EV/EBITDA); they come back as None, which aihf treats as unknown.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import requests
import yfinance as yf

from hedge_fund.data.models import (
    CompanyFacts, CompanyNews, Earnings, EarningsData, EarningsRecord, FinancialMetrics, InsiderTrade, Price, PriceSnapshot,
)

CACHE = Path(os.environ.get("AIHF_GLUE_CACHE", Path.home() / ".hedge-fund" / "cache" / "alpha_glue"))
SEC_USER_AGENT = os.environ.get("SEC_EDGAR_USER_AGENT") or "TradingAgents-glue/0.1 (research; contact@example.com)"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FORM4 = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{name}"
ALPHA_VANTAGE = "https://www.alphavantage.co/query"
THROTTLE = {"sec": 0.12, "av": 0.45}

QUARTER, HALF, NINE_MONTHS, YEAR = (60, 115), (150, 200), (240, 290), (300, 400)
REVENUE = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet")
NET_INCOME, OPERATING_INCOME, GROSS_PROFIT = ("NetIncomeLoss",), ("OperatingIncomeLoss",), ("GrossProfit",)
OPERATING_CASH, CAPEX = ("NetCashProvidedByUsedInOperatingActivities",), ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets")
EPS = ("EarningsPerShareDiluted",)
EQUITY = ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest")
ASSETS, LIABILITIES = ("Assets",), ("Liabilities",)
CURRENT_ASSETS, CURRENT_LIABILITIES = ("AssetsCurrent",), ("LiabilitiesCurrent",)
CASH = ("CashAndCashEquivalentsAtCarryingValue",)
DEBT = ("LongTermDebt", "LongTermDebtNoncurrent", "DebtLongtermAndShorttermCombinedAmount")


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def series(us_gaap: dict, tags: tuple[str, ...], as_of: str, span: tuple[int, int] | None, annual_form: bool = False) -> dict:
    """{(start, end): (value, filed)} as known on ``as_of``: a period keeps its latest filing by then.

    The first tag that reports a period wins; values are never added across tags.
    """
    out: dict[tuple[str, str], tuple[float, str]] = {}
    for tag in tags:
        for facts in (us_gaap.get(tag) or {}).get("units", {}).values():
            latest: dict[tuple[str, str], dict] = {}
            for fact in facts:
                if fact["filed"] > as_of:
                    continue
                if span is not None and ("start" not in fact or not span[0] <= _days(fact["start"], fact["end"]) <= span[1]):
                    continue
                if annual_form and not fact.get("form", "").startswith(("10-K", "20-F", "40-F")):
                    continue
                key = (fact.get("start", ""), fact["end"])
                if key not in latest or fact["filed"] >= latest[key]["filed"]:
                    latest[key] = fact
            for key, fact in latest.items():
                out.setdefault(key, (fact["val"], fact["filed"]))
    return out


def ttm(us_gaap: dict, tags: tuple[str, ...], as_of: str) -> tuple[float, str, str] | None:
    """(value, period end, latest filing date) for the twelve months to the newest filed period."""
    annual = series(us_gaap, tags, as_of, YEAR, annual_form=True)
    if not annual:
        return None
    (_, fiscal_end), (fiscal, filed) = max(annual.items(), key=lambda item: item[0][1])
    interim = {k: v for span in (QUARTER, HALF, NINE_MONTHS) for k, v in series(us_gaap, tags, as_of, span).items()}
    later = {k: v for k, v in interim.items() if k[1] > fiscal_end}
    if not later:
        return fiscal, fiscal_end, filed
    (start, end), (current, current_filed) = max(later.items(), key=lambda item: (item[0][1], _days(*item[0])))
    length = _days(start, end)
    target = date.fromisoformat(end) - timedelta(days=365)
    prior = next((v for (s, e), (v, _) in interim.items() if abs(_days(s, e) - length) <= 10
                  and abs((date.fromisoformat(e) - target).days) <= 10), None)
    if prior is None:
        return fiscal, fiscal_end, filed
    return fiscal + current - prior, end, max(filed, current_filed)


def instant(us_gaap: dict, tags: tuple[str, ...], as_of: str) -> tuple[float, str, str] | None:
    values = series(us_gaap, tags, as_of, None)
    if not values:
        return None
    (_, end), (value, filed) = max(values.items(), key=lambda item: item[0][1])
    return value, end, filed


def shares_outstanding(dei: dict, as_of: str) -> float | None:
    entries = [f for f in (dei.get("EntityCommonStockSharesOutstanding") or {}).get("units", {}).get("shares", []) if f["filed"] <= as_of]
    if not entries:
        return None
    filed = max(f["filed"] for f in entries)
    end = max(f["end"] for f in entries if f["filed"] == filed)
    return float(sum(f["val"] for f in entries if f["filed"] == filed and f["end"] == end))


def parse_form4(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    owner = root.findtext(".//reportingOwner/reportingOwnerId/rptOwnerName") or "unknown"
    relation = root.find(".//reportingOwner/reportingOwnerRelationship")
    director = relation is not None and (relation.findtext("isDirector") or "").lower() in ("1", "true")
    title = (relation.findtext("officerTitle") if relation is not None else "") or ("Director" if director else "")
    rows = []
    for t in root.findall(".//nonDerivativeTransaction"):
        try:
            shares = float(t.findtext("transactionAmounts/transactionShares/value"))
            price = float(t.findtext("transactionAmounts/transactionPricePerShare/value") or 0)
            after = t.findtext("postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        except (TypeError, ValueError):
            continue
        rows.append({"owner": owner, "title": title.strip(), "director": director, "code": t.findtext("transactionCoding/transactionCode") or "",
                     "day": t.findtext("transactionDate/value") or "", "shares": shares, "price": price,
                     "after": float(after) if after else None})
    return rows


class AlphaClient:
    """aihf DataClient over Yahoo, SEC EDGAR and Alpha Vantage."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def close(self) -> None:
        pass

    def _get(self, url: str, params: dict | None = None, kind: str = "sec", cache: str | None = None, text: bool = False):
        path = CACHE / f"{hashlib.sha1((cache or url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()}.{'txt' if text else 'json'}"
        if path.exists() and (cache is None or time.time() - path.stat().st_mtime < 86400):
            return path.read_text() if text else json.loads(path.read_text())
        time.sleep(THROTTLE[kind])
        headers = {"User-Agent": SEC_USER_AGENT} if kind == "sec" else {}
        if kind == "av":
            params = {**(params or {}), "apikey": os.environ["ALPHA_VANTAGE_API_KEY"]}
        reply = requests.get(url, params=params, headers=headers, timeout=60)
        reply.raise_for_status()
        data = reply.text if text else reply.json()
        if kind == "av" and isinstance(data, dict) and ("Information" in data or "Error Message" in data):
            raise RuntimeError(f"Alpha Vantage: {str(data.get('Information') or data.get('Error Message'))[:120]}")
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(data if text else json.dumps(data))
        return data

    def _cik(self, ticker: str) -> str | None:
        table = self._get(SEC_TICKERS, cache="tickers")
        return next((f"{int(e['cik_str']):010d}" for e in table.values() if e["ticker"].upper() == ticker.upper()), None)

    def _facts(self, ticker: str) -> dict:
        cik = self._cik(ticker)
        if cik is None:
            return {}
        return self._get(SEC_FACTS.format(cik=cik), cache=f"facts-{cik}")["facts"]

    def get_prices(self, ticker: str, start_date: str, end_date: str, interval: str = "day", interval_multiplier: int = 1) -> list[Price]:
        if interval != "day":
            raise NotImplementedError("this client serves daily bars only")
        frame = yf.Ticker(ticker).history(start=start_date, end=(date.fromisoformat(end_date) + timedelta(days=1)).isoformat(), auto_adjust=False)
        if frame is None:
            raise RuntimeError(f"Yahoo returned nothing for {ticker}")
        return [Price(open=float(r.Open), close=float(r.Close), high=float(r.High), low=float(r.Low), volume=int(r.Volume),
                      time=f"{ts.strftime('%Y-%m-%d')}T00:00:00") for ts, r in frame.iterrows()]

    def get_snapshot(self, ticker: str) -> PriceSnapshot | None:
        frame = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
        if frame is None or frame.empty:
            return None
        last = frame.iloc[-1]
        return PriceSnapshot(ticker=ticker, price=float(last.Close), time=frame.index[-1].strftime("%Y-%m-%dT00:00:00"))

    def _close_on(self, ticker: str, as_of: str) -> float | None:
        """The last close on or before ``as_of``, from one history fetched per ticker."""
        if not hasattr(self, "_closes"):
            self._closes = {}
        if ticker not in self._closes:
            frame = yf.Ticker(ticker).history(start="2012-01-01", auto_adjust=False)
            if frame is None or frame.empty:
                raise RuntimeError(f"Yahoo returned no price history for {ticker}")
            self._closes[ticker] = {ts.strftime("%Y-%m-%d"): float(close) for ts, close in frame.Close.items()}
        days = [d for d in self._closes[ticker] if d <= as_of]
        return self._closes[ticker][max(days)] if days else None

    def get_market_cap(self, ticker: str, end_date: str) -> float | None:
        facts = self._facts(ticker)
        shares, price = shares_outstanding(facts.get("dei", {}), end_date), self._close_on(ticker, end_date)
        return shares * price if shares and price else None

    def get_financial_metrics(self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10) -> list[FinancialMetrics]:
        """Newest first: the twelve months to each filing, each as known on the day it was filed.

        The agents want a year or more of rows, so each older row is the same calculation as of the day
        before the newer one's filing, which steps back one report at a time.
        """
        if period != "ttm":
            return []
        facts, rows, as_of = self._facts(ticker), [], end_date
        for _ in range(limit):
            row = self._metrics_at(ticker, facts, as_of)
            if row is None or (rows and row.report_period >= rows[-1].report_period):
                break
            rows.append(row)
            as_of = (date.fromisoformat(row.filing_date) - timedelta(days=1)).isoformat()
        return rows

    def _metrics_at(self, ticker: str, facts: dict, end_date: str) -> FinancialMetrics | None:
        gaap = facts.get("us-gaap", {})
        revenue, income, op, gross = (ttm(gaap, t, end_date) for t in (REVENUE, NET_INCOME, OPERATING_INCOME, GROSS_PROFIT))
        if not revenue and not income:
            return None
        a_year_ago = (date.fromisoformat(end_date) - timedelta(days=365)).isoformat()
        eps, ocf, capex = ttm(gaap, EPS, end_date), ttm(gaap, OPERATING_CASH, end_date), ttm(gaap, CAPEX, end_date)
        equity, assets, liabilities, cur_a, cur_l, cash, debt = (instant(gaap, t, end_date) for t in (
            EQUITY, ASSETS, LIABILITIES, CURRENT_ASSETS, CURRENT_LIABILITIES, CASH, DEBT))
        shares, price = shares_outstanding(facts.get("dei", {}), end_date), self._close_on(ticker, end_date)
        cap = shares * price if shares and price else None
        value = lambda item: item[0] if item else None
        ratio = lambda a, b: a / b if a is not None and b else None
        fcf = value(ocf) - abs(value(capex)) if ocf and capex else None
        growth = lambda now, then: (now[0] / then[0] - 1) if now and then and then[0] > 0 else None
        filed = max((x[2] for x in (revenue, income, op, gross, eps) if x), default=None)
        return FinancialMetrics(
            ticker=ticker, report_period=(revenue or income)[1], period="ttm", currency="USD", filing_date=filed,
            market_cap=cap, price_to_earnings_ratio=ratio(price, value(eps)) if eps and eps[0] > 0 else None,
            price_to_book_ratio=ratio(cap, value(equity)) if equity and equity[0] > 0 else None,
            price_to_sales_ratio=ratio(cap, value(revenue)), free_cash_flow_yield=ratio(fcf, cap),
            gross_margin=ratio(value(gross), value(revenue)), operating_margin=ratio(value(op), value(revenue)),
            net_margin=ratio(value(income), value(revenue)), return_on_equity=ratio(value(income), value(equity)),
            return_on_assets=ratio(value(income), value(assets)), current_ratio=ratio(value(cur_a), value(cur_l)),
            debt_to_equity=ratio(value(debt), value(equity)), debt_to_assets=ratio(value(liabilities), value(assets)),
            revenue_growth=growth(revenue, ttm(gaap, REVENUE, a_year_ago)), earnings_growth=growth(income, ttm(gaap, NET_INCOME, a_year_ago)),
            earnings_per_share_growth=growth(eps, ttm(gaap, EPS, a_year_ago)), earnings_per_share=value(eps),
            book_value_per_share=ratio(value(equity), shares), free_cash_flow_per_share=ratio(fcf, shares),
        )

    def get_news(self, ticker: str, end_date: str, start_date: str | None = None, limit: int = 1000) -> list[CompanyNews]:
        start = start_date or (date.fromisoformat(end_date) - timedelta(days=30)).isoformat()
        data = self._get(ALPHA_VANTAGE, {"function": "NEWS_SENTIMENT", "tickers": ticker, "limit": str(min(limit, 200)),
                                         "time_from": start.replace("-", "") + "T0000", "time_to": end_date.replace("-", "") + "T2359"}, kind="av")
        items = []
        for a in data.get("feed", []):
            about = next((t for t in a.get("ticker_sentiment", []) if t.get("ticker") == ticker), None)
            if about and float(about.get("relevance_score", 0)) >= 0.3:
                p = a["time_published"]
                items.append(CompanyNews(ticker=ticker, title=a["title"], source=a.get("source", ""), url=a.get("url"),
                                         date=f"{p[:4]}-{p[4:6]}-{p[6:8]}T{p[9:11]}:{p[11:13]}:{p[13:15]}"))
        return items

    def get_insider_trades(self, ticker: str, end_date: str, start_date: str | None = None, limit: int = 1000) -> list[InsiderTrade]:
        cik = self._cik(ticker)
        if cik is None:
            return []
        since = start_date or (date.fromisoformat(end_date) - timedelta(days=365)).isoformat()
        recent = self._get(SEC_SUBMISSIONS.format(cik=cik), cache=f"submissions-{cik}").get("filings", {}).get("recent", {})
        trades: list[InsiderTrade] = []
        for i, form in enumerate(recent.get("form", [])):
            filed = recent["filingDate"][i]
            if form != "4" or not since <= filed <= end_date or len(trades) >= limit:
                continue
            name = recent["primaryDocument"][i].split("/")[-1]
            url = SEC_FORM4.format(cik=int(cik), accession=recent["accessionNumber"][i].replace("-", ""), name=name)
            try:
                rows = parse_form4(self._get(url, text=True))
            except (requests.RequestException, ET.ParseError):
                continue
            for r in rows:
                if r["code"] in ("P", "S"):
                    sign = 1 if r["code"] == "P" else -1
                    trades.append(InsiderTrade(ticker=ticker, name=r["owner"], filing_date=filed, is_board_director=r["director"],
                                               title=r["title"] or None, transaction_date=r["day"] or None, transaction_shares=sign * r["shares"],
                                               transaction_price_per_share=r["price"], transaction_value=sign * r["shares"] * r["price"],
                                               shares_owned_after_transaction=r["after"]))
        return trades

    def get_company_facts(self, ticker: str) -> CompanyFacts | None:
        cik = self._cik(ticker)
        if cik is None:
            return None
        sub = self._get(SEC_SUBMISSIONS.format(cik=cik), cache=f"submissions-{cik}")
        return CompanyFacts(ticker=ticker, name=sub.get("name"), cik=cik, sic_code=sub.get("sic"), sic_industry=sub.get("sicDescription"),
                            exchange=(sub.get("exchanges") or [None])[0])

    def _earnings(self, ticker: str) -> list[EarningsRecord]:
        data = self._get(ALPHA_VANTAGE, {"function": "EARNINGS", "symbol": ticker}, kind="av", cache=f"earnings-{ticker}")
        records = []
        for q in data.get("quarterlyEarnings", []):
            try:
                actual, estimate = float(q["reportedEPS"]), float(q["estimatedEPS"])
            except (KeyError, TypeError, ValueError):
                continue
            surprise = "BEAT" if actual > estimate else "MISS" if actual < estimate else "MEET"
            records.append(EarningsRecord(
                ticker=ticker, report_period=q["fiscalDateEnding"], source_type="8-K", filing_date=q.get("reportedDate"),
                quarterly=EarningsData(earnings_per_share=actual, estimated_earnings_per_share=estimate, eps_surprise=surprise)))
        return sorted(records, key=lambda r: r.report_period, reverse=True)

    def get_earnings_history(self, ticker: str, limit: int = 12) -> list[EarningsRecord]:
        return self._earnings(ticker)[:limit]

    def get_earnings(self, ticker: str) -> Earnings | None:
        latest = next(iter(self._earnings(ticker)), None)
        return None if latest is None else Earnings(ticker=ticker, report_period=latest.report_period, quarterly=latest.quarterly)
