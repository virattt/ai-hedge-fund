"""On-demand BeliefState company discovery and current investor research."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from http.client import HTTPException, HTTPSConnection
from threading import Lock
from time import monotonic
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, Field, HttpUrl, StringConstraints, model_validator

API_KEY_ENV = "BELIEFSTATE_API_KEY"
HOST = "beliefstate.ai"
CACHE_SECONDS = 60
Ticker = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9][A-Z0-9.-]{0,31}$")]
ResearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ResearchError(Exception):
    """A research request failed or returned an unexpected response."""


class Company(BaseModel):
    ticker: Ticker
    name: ResearchText
    direct_research: bool
    exchange: str | None = None


class _CompanyCoverage(BaseModel):
    ticker: Ticker
    security_name: ResearchText


class _Discovery(BaseModel):
    results: list[Company]


class _Coverage(BaseModel):
    schema_version: Literal["1"]
    resource: Literal["beliefs"]
    as_of: AwareDatetime
    tickers: list[Ticker]
    coverage: list[_CompanyCoverage]
    discovery: _Discovery | None = None


class Evidence(BaseModel):
    source_url: HttpUrl
    published_at: AwareDatetime | None
    source_coverage: str = "unknown"


class Unknown(BaseModel):
    field: str
    reason: str


class ResearchObject(BaseModel):
    statement: ResearchText
    status: str
    evidence: list[Evidence] = []
    checking_evidence: list[Evidence] = []
    unknowns: list[Unknown] = []


class _Person(BaseModel):
    name: str


class Belief(BaseModel):
    person: _Person
    thesis: ResearchText
    direction: str
    action: str | None = None
    target: str | None = None
    time_horizon: str | None = None
    evidence: list[Evidence] = Field(min_length=1)
    risks: list[ResearchObject] = Field(max_length=3)
    catalysts: list[ResearchObject] = Field(max_length=3)
    qualifications: list[str]
    unknowns: list[Unknown]
    omitted_risk_count: int = Field(ge=0)
    omitted_catalyst_count: int = Field(ge=0)
    detail_url: HttpUrl


class _BriefCoverage(BaseModel):
    completeness: Literal["complete_within_scope", "bounded", "no_fit"]
    omitted_belief_count: int = Field(ge=0)


class _BriefScope(BaseModel):
    ticker: Ticker


class _QualityGap(BaseModel):
    reason: str
    detail_url: HttpUrl


class CurrentBrief(BaseModel):
    schema_version: Literal["1"]
    resource: Literal["brief"]
    view: Literal["current"]
    as_of: AwareDatetime
    scope: _BriefScope
    beliefs: list[Belief] = Field(max_length=3)
    coverage: _BriefCoverage
    warnings: list[str]
    quality_gaps: list[_QualityGap]
    detail_reference: str | None = None

    @model_validator(mode="after")
    def _consistent_dates(self):
        if self.as_of > datetime.now(timezone.utc):
            raise ValueError("future research cutoff")
        for belief in self.beliefs:
            evidence = list(belief.evidence)
            for item in belief.risks + belief.catalysts:
                evidence.extend(item.evidence)
                evidence.extend(item.checking_evidence)
            if any(source.published_at is not None and source.published_at > self.as_of for source in evidence):
                raise ValueError("source published after research cutoff")
        if self.coverage.completeness == "no_fit" and self.beliefs:
            raise ValueError("unexpected views in a no-fit brief")
        return self


def _read(path: str, params: dict[str, str], *, api_key: str = "", request_id: str = "") -> dict:
    headers = {"Accept": "application/json"}
    if api_key:
        headers.update({"Authorization": f"Bearer {api_key}", "X-Request-ID": request_id})
    connection = HTTPSConnection(HOST, timeout=45 if api_key else 15)
    try:
        connection.request("GET", f"{path}?{urlencode(params)}", headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            recovery = {
                401: "Check your BeliefState API key.",
                402: "Check your BeliefState research allowance or credit.",
                403: "Check this key's access to current research.",
                404: "Current research is unavailable for this request.",
                409: "This request was already processed.",
                429: "The service is rate limited. Try later.",
            }.get(response.status, "The research service is unavailable. Try later.")
            raise ResearchError(f"BeliefState HTTP {response.status}. {recovery}")
        limit = 65_536 if api_key else 1_048_576
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ResearchError("The BeliefState response exceeded the size limit.")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
        return payload
    except (OSError, HTTPException, ValueError, RecursionError):
        raise ResearchError("Could not read the BeliefState response.") from None
    finally:
        connection.close()


class BeliefStateClient:
    """Keep fresh reads for one account in memory for this app session."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key.strip()
        self._read_lock = Lock()
        self._companies: dict[str, tuple[float, list[Company]]] = {}
        self._briefs: dict[str, tuple[float, CurrentBrief | None]] = {}

    def search(self, query: str) -> list[Company]:
        query = query.strip()
        if not 1 <= len(query) <= 80:
            raise ResearchError("Enter a ticker or company name of up to 80 characters.")
        cached = self._companies.get(query.upper())
        if cached and monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        try:
            coverage = _Coverage.model_validate(_read("/v1/tickers", {"q": query}))
            released = set(coverage.tickers)
            if released != {company.ticker for company in coverage.coverage}:
                raise ValueError("inconsistent released coverage")
        except ValueError:
            raise ResearchError("BeliefState returned an invalid company search response.") from None
        companies = {company.ticker: company for company in coverage.discovery.results} if coverage.discovery else {}
        for company in companies.values():
            company.direct_research = company.ticker in released
        for company in coverage.coverage:
            companies[company.ticker] = Company(ticker=company.ticker, name=company.security_name, direct_research=True)
        result = list(companies.values())
        self._companies[query.upper()] = (monotonic(), result)
        return result

    def read(self, ticker: str, *, cancelled: Callable[[], bool]) -> CurrentBrief | None:
        with self._read_lock:
            ticker = ticker.strip().upper()
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,31}", ticker):
                raise ResearchError("Select a single company ticker.")
            cached = self._briefs.get(ticker)
            if cached and monotonic() - cached[0] < CACHE_SECONDS:
                return cached[1]
            if cancelled():
                raise ResearchError("Research cancelled.")
            companies = self.search(ticker)
            if not any(company.ticker == ticker and company.direct_research for company in companies):
                self._briefs[ticker] = (monotonic(), None)
                return None
            if not self._api_key:
                raise ResearchError(f"Set {API_KEY_ENV} to your BeliefState API key, or press Ctrl+K to add it.")
            if cancelled():
                raise ResearchError("Research cancelled.")
            request_id = str(uuid4())
            try:
                brief = CurrentBrief.model_validate(_read(
                    "/v1/brief", {"ticker": ticker, "detail": "current", "max_results": "3"},
                    api_key=self._api_key, request_id=request_id,
                ))
                if brief.scope.ticker != ticker:
                    raise ValueError("mismatched ticker")
            except (ResearchError, ValueError) as exc:
                message = str(exc) if isinstance(exc, ResearchError) else "BeliefState returned an invalid current brief."
                raise ResearchError(f"{message} Request ID {request_id}. Check account usage before requesting again.") from None
            self._briefs[ticker] = (monotonic(), brief)
            return brief
