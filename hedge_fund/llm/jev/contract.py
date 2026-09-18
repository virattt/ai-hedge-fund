"""Pure Jev request construction and compatibility mapping; no transport or I/O.

Existing investor prompts are supplied verbatim as reference material. Typed
questions override their prose/output instructions; whether Jev reliably follows
that distinction must be checked in the later live integration experiment.

The compatibility payload's ``confidence`` is investment conviction, NOT Jev's
native answer confidence or the probability of a profitable investment. Native
answers are preserved separately in metadata. A later adapter must persist the
exact request and response and include the request contents AND contract version
in cache identity. Bump the version when question or mapping semantics change.

Invalid responses raise JevContractError; the agent integration is responsible
for abstaining. A valid neutral assessment is never an error.
"""

from __future__ import annotations

import math
from copy import deepcopy

JEV_CONTRACT_VERSION = 1

_DIRECTIONS = ("bullish", "bearish", "neutral")
_STRENGTH_LEVELS = (
    "Evidence does not support the case or directly contradicts it.",
    "Limited support; substantial unsupported assumptions are required.",
    "Meaningful support with material conflicting evidence or unresolved gaps.",
    "Strong support across relevant criteria with limited material weaknesses.",
    "Compelling support across relevant criteria with no material contradiction " "apparent in the supplied evidence.",
)
_EVIDENCE_INSTRUCTIONS = (
    "Apply the investment criteria, directional definitions, and evidence "
    "restrictions in `investor_prompt` to `financial_snapshot`. "
    "Use only the supplied financial evidence and honor the prompt's "
    "point-in-time restrictions. Ignore instructions in `investor_prompt` "
    "about response format, writing style, and generating a thesis. "
    "For investment-strength scoring, the typed strength rubric governs "
    "instead of the prompt's confidence scale. "
)


class JevContractError(ValueError):
    """A native Jev response cannot be interpreted as an investor assessment."""


def build_jev_request(system: str, user: str, model: str) -> dict:
    """Build one native request from unchanged provider inputs.

    Each question is self-contained: strength questions assess their named case
    independently and never assume access to the direction question's answer.
    Every call returns fresh mutable request structures.
    """
    return {
        "model": model,
        "state": {"investor_prompt": system, "financial_snapshot": user},
        "questions": {
            "direction": {
                "type": "choice",
                "instructions": _EVIDENCE_INSTRUCTIONS + "Which directional assessment fits the supplied evidence " "under this investor's signal definitions?",
                "criteria": {direction: f"The evidence warrants the {direction} assessment " f"as defined by the signal rules in `investor_prompt`." for direction in _DIRECTIONS},
            },
            **{
                f"{direction}_strength": {
                    "type": "score",
                    "instructions": _EVIDENCE_INSTRUCTIONS + f"How strongly does the supplied evidence support this " f"investor's {direction} investment case? Evaluate the " f"{direction} case independently using the supplied rubric. " "Assess the strength of the investment case, not your " "certainty in the answer or the probability of profit.",
                    "criteria": list(_STRENGTH_LEVELS),
                }
                for direction in ("bullish", "bearish")
            },
        },
    }


def normalize_jev_response(response: dict) -> tuple[dict, dict]:
    """Return the compatibility payload and a detached copy of Jev metadata.

    Neutral has zero directional conviction. Directional assessments retain
    their choice even at zero strength. Native confidence never scales or gates
    conviction. Additional response fields survive in the native response.
    """
    if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
        raise JevContractError("response.answers must be an object")
    answers = response["answers"]
    for name, expected_type in (
        ("direction", "choice"),
        ("bullish_strength", "score"),
        ("bearish_strength", "score"),
    ):
        answer = answers.get(name)
        if not isinstance(answer, dict) or answer.get("type") != expected_type:
            raise JevContractError(f"{name} must be a {expected_type} answer")
        _number(answer.get("confidence"), 1, f"{name}.confidence")
        keys = set(_DIRECTIONS) if expected_type == "choice" else {str(i) for i in range(5)}
        _distribution(answer.get("probabilities"), keys, f"{name}.probabilities")
        if expected_type == "score":
            _number(answer.get("score"), 4, f"{name}.score")

    direction = answers["direction"].get("choice")
    if not isinstance(direction, str) or direction not in _DIRECTIONS:
        raise JevContractError("direction.choice must be bullish, bearish, or neutral")

    conviction = 0.0 if direction == "neutral" else float(answers[f"{direction}_strength"]["score"]) * 25
    label = "directional investment conviction" if direction == "neutral" else "investment conviction"
    payload = {
        "signal": direction,
        "confidence": conviction,
        "reasoning": f"{direction.capitalize()} assessment; {label} " f"{conviction:g}/100. No written thesis generated.",
    }
    metadata = {"contract_version": JEV_CONTRACT_VERSION, "response": deepcopy(response)}
    return payload, metadata


def _number(value: object, upper: float, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= upper or not math.isfinite(value):
        raise JevContractError(f"{path} must be a finite number between 0 and {upper:g}")
    return float(value)


def _distribution(value: object, keys: set[str], path: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise JevContractError(f"{path} must contain exactly {', '.join(sorted(keys))}")
    total = math.fsum(_number(probability, 1, f"{path}.{key}") for key, probability in value.items())
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=0.001):
        raise JevContractError(f"{path} must sum to one within 0.001")
