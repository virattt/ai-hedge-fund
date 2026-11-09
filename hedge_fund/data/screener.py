"""The stock screener: which companies passed a set of filters on a date.

Pure models and the vocabulary check. No I/O here: ``FDClient.screen`` and
``FDClient.screener_fields`` fetch, these shape and judge.

WHY point-in-time: a backtest asks "which companies could this fund have
picked on date X, from numbers that were public on X". The screener's
``as_of`` answers from each company's newest filing made public on or
before X (``filing_date <= as_of``), and drops a company whose latest
period is more than 180 days old. A screen without a date reads today's
numbers, which is lookahead inside a backtest, so the client refuses one.

Known limits of the source (checked 2026-11-08):
- A filter on a field drops companies with no value for it.
- No volume, momentum, or price-return fields; ``stock_price`` is refused
  with ``as_of``. Price-based factors come from the price history.
- ``market_cap`` and the price ratios are as computed when the filing was
  processed, not at the close of ``as_of``.
- The company set is today's listings. Companies delisted since are absent
  from past dates (survivorship).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Operator = Literal["gt", "lt", "gte", "lte", "eq", "in"]
COMPANY_OPERATORS = frozenset({"eq", "in"})
COMPANY_FIELDS = frozenset({"sector", "industry"})
# The eligible set is about 2,000 names; ranking is local, so the server never cuts.
SCREEN_LIMIT = 20_000
# Every row carries these. Everything else in a row is a number the request asked for.
STAMP_KEYS = frozenset({"ticker", "filing_date", "report_period", "currency", "sector", "industry"})


class ScreenFilter(BaseModel):
    """One condition, in the API's own shape: ``model_dump()`` is the request object."""

    field: str
    operator: Operator
    value: float | str | list[float] | list[str]


class OrderBy(BaseModel):
    """A server-side sort on a numeric field; the field joins every row."""

    field: str
    direction: Literal["asc", "desc"] = "desc"


class ScreenRow(BaseModel):
    """One company that passed: the filing that answered, and the numbers asked for."""

    model_config = {"extra": "ignore"}

    ticker: str
    filing_date: str
    report_period: str
    currency: str | None = None
    sector: str | None = None
    industry: str | None = None
    values: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def from_api(cls, row: dict) -> ScreenRow:
        stamps = {key: value for key, value in row.items() if key in STAMP_KEYS}
        values = {
            key: float(value) for key, value in row.items()
            if key not in STAMP_KEYS and isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        return cls(**stamps, values=values)


class ScreenerFields(BaseModel):
    """The screener's vocabulary, as ``GET /financials/search/screener/filters`` serves it.

    A mandate's filters are checked against this before Go, so a typo or a
    field the point-in-time path cannot serve fails at authoring time, not
    on the first rebalance day."""

    numeric: frozenset[str]
    sectors: frozenset[str]
    industries: frozenset[str]
    operators: frozenset[str]
    # The filing records behind ``as_of`` carry every screenable number but these.
    unavailable_as_of: frozenset[str] = frozenset({"stock_price"})

    @classmethod
    def from_api(cls, body: dict) -> ScreenerFields:
        numeric: set[str] = set()
        for group, fields in body.get("metrics", {}).items():
            if group != "company":
                numeric.update(fields)
        # Aliases map a public name to the raw one (pe_ratio -> price_to_earnings_ratio); both are accepted.
        numeric.update(body.get("aliases", {}).values())
        values = body.get("company_filters", {}).get("values", {})
        return cls(
            numeric=frozenset(numeric),
            sectors=frozenset(values.get("sector", [])),
            industries=frozenset(values.get("industry", [])),
            operators=frozenset(body.get("operators", [])),
        )

    def problems(self, filters: list[ScreenFilter], order_by: OrderBy | None = None) -> list[str]:
        """Every reason this request would fail or lie, in plain words. Empty means sound."""
        found: list[str] = []
        for item in filters:
            found.extend(self._filter_problems(item))
        if order_by is not None and order_by.field not in self.numeric:
            found.append(f"order_by '{order_by.field}' is not a numeric screener field")
        elif order_by is not None and order_by.field in self.unavailable_as_of:
            found.append(f"order_by '{order_by.field}' is not available point-in-time")
        return found

    def _filter_problems(self, item: ScreenFilter) -> list[str]:
        if item.field == "ticker":
            if item.operator not in COMPANY_OPERATORS:
                return [f"'ticker' takes eq or in, not {item.operator}"]
            return [] if _all_strings(item.value) else ["'ticker' needs a ticker or a list of tickers"]
        if item.field in COMPANY_FIELDS:
            return self._company_problems(item)
        if item.field not in self.numeric:
            return [f"'{item.field}' is not a screener field"]
        if item.field in self.unavailable_as_of:
            return [f"'{item.field}' is not available point-in-time; the filing records do not carry it"]
        if item.operator == "in":
            return [] if _all_numbers(item.value) else [f"'{item.field}' with in needs a list of numbers"]
        return [] if _is_number(item.value) else [f"'{item.field}' needs a number, not {item.value!r}"]

    def _company_problems(self, item: ScreenFilter) -> list[str]:
        found: list[str] = []
        if item.operator not in COMPANY_OPERATORS:
            found.append(f"'{item.field}' takes eq or in, not {item.operator}")
        known = {name.lower() for name in (self.sectors if item.field == "sector" else self.industries)}
        names = item.value if isinstance(item.value, list) else [item.value]
        for name in names:
            if not isinstance(name, str) or name.lower() not in known:
                found.append(f"{name!r} is not a {item.field} the screener knows")
        return found


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _all_numbers(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_number(item) for item in value)


def _all_strings(value: object) -> bool:
    if isinstance(value, str):
        return True
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) for item in value)
