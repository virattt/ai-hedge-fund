"""Evidence host-allowlisting + substantiation (PRD v4 §9.6, §11.5, R2).

``source_type`` is derived from an allowlisted host — never accepted from the LLM
or user. Substantiation is a deterministic claim↔text overlap check: a fetched
page that does not mention the claim's terms (e.g. a rate-limit/login page) does
not count, even with HTTP 200. Phase 0 operates on user-provided excerpts; live
fetching + SSRF hardening is an expansion phase (PRD Phase 7/8).
"""

import re
from urllib.parse import urlparse

from src.storage.models import SourceType

# Base domains → source_type. Subdomains match via endswith("." + base).
DEFAULT_HOST_ALLOWLIST: dict[str, SourceType] = {
    "sec.gov": SourceType.FILING,
    "uspto.gov": SourceType.PATENT,
    "patents.google.com": SourceType.PATENT,
    "federalregister.gov": SourceType.REGULATORY,
    "europa.eu": SourceType.REGULATORY,
    "reuters.com": SourceType.NEWS,
    "bloomberg.com": SourceType.NEWS,
    "wsj.com": SourceType.NEWS,
}

_WORD_RE = re.compile(r"[a-z0-9]+")
_MIN_OVERLAP = 0.20
_MIN_EXCERPT_WORDS = 8


def host_of(url: str) -> str | None:
    try:
        netloc = urlparse(url).netloc.lower()
    except ValueError:
        return None
    return netloc.split("@")[-1].split(":")[0] or None


def source_type_for_host(host: str | None, allowlist: dict[str, SourceType] = DEFAULT_HOST_ALLOWLIST) -> SourceType:
    """Map a host to a source_type via the allowlist; unknown hosts → UNVERIFIED."""
    if not host:
        return SourceType.UNVERIFIED
    for base, stype in allowlist.items():
        if host == base or host.endswith("." + base):
            return stype
    return SourceType.UNVERIFIED


def _tokens(text: str | None) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if len(w) >= 3}


def is_substantiated(claim: str | None, excerpt: str | None, min_overlap: float = _MIN_OVERLAP) -> bool:
    """True iff the excerpt materially mentions the claim's terms.

    Guards against URL-flooding with on-host-but-irrelevant pages: an excerpt that
    does not overlap the claim fails regardless of HTTP status.
    """
    claim_tokens = _tokens(claim)
    excerpt_tokens = _tokens(excerpt)
    if not claim_tokens or len(excerpt_tokens) < _MIN_EXCERPT_WORDS:
        return False
    overlap = len(claim_tokens & excerpt_tokens) / len(claim_tokens)
    return overlap >= min_overlap


def classify_reference(
    *,
    source_url: str,
    claim_summary: str | None,
    excerpt: str | None,
    allowlist: dict[str, SourceType] = DEFAULT_HOST_ALLOWLIST,
) -> dict:
    """Derive {source_host, source_type, substantiated} deterministically."""
    host = host_of(source_url)
    stype = source_type_for_host(host, allowlist)
    substantiated = stype is not SourceType.UNVERIFIED and is_substantiated(claim_summary, excerpt)
    return {"source_host": host, "source_type": stype, "substantiated": substantiated}
