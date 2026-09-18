"""Pure Jev contract tests: no credentials, transport, or provider construction."""

import json
import math
from copy import deepcopy

import pytest

from hedge_fund.llm import PromptCache
from hedge_fund.llm.contract import (
    build_jev_request,
    JEV_CONTRACT_VERSION,
    JevContractError,
    normalize_jev_response,
)
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, BuffettAgent, LLMAgent

_PERSONAS = [cls for cls in ALPHA_MODEL_REGISTRY.values() if issubclass(cls, LLMAgent)]


class NoNetworkLLM:
    model = "unused"

    def complete(self, system, user):
        raise AssertionError("contract tests must not call a provider")


def _response(direction="bullish", bullish=3.2, bearish=1.6):
    levels = build_jev_request("", "", "jev-test")["questions"]["bullish_strength"]["criteria"]

    def strength(score):
        lower = math.floor(score)
        probabilities = {str(i): 0.0 for i in range(5)}
        probabilities[str(lower)] = 1 - (score - lower)
        if lower < 4:
            probabilities[str(lower + 1)] = score - lower
        return {
            "type": "score",
            "score": score,
            "confidence": 0.4,
            "probabilities": probabilities,
            "legend": {str(i): text for i, text in enumerate(levels)},
        }

    return {
        "model": "jev-test-resolved",
        "answers": {
            "direction": {
                "type": "choice",
                "choice": direction,
                "confidence": 0.6,
                "probabilities": {name: 0.8 if name == direction else 0.1 for name in ("bullish", "bearish", "neutral")},
            },
            "bullish_strength": strength(bullish),
            "bearish_strength": strength(bearish),
        },
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


@pytest.mark.parametrize("persona", _PERSONAS, ids=lambda cls: cls.__name__)
def test_existing_persona_inputs_are_preserved(persona, tmp_path):
    agent = persona(llm=NoNetworkLLM(), cache=PromptCache(tmp_path))
    system = agent.get_system_prompt()
    user = "  Company: TEST\nFinancial snapshot: café\n\n"
    request = build_jev_request(system, user, "jev-test")

    assert request["model"] == "jev-test"
    assert request["state"] == {"investor_prompt": system, "financial_snapshot": user}
    assert agent.get_system_prompt() == system
    assert "Respond with JSON" in request["state"]["investor_prompt"]
    assert "most recent filing date" in request["state"]["investor_prompt"]


def test_questions_are_self_contained_and_requests_do_not_share_mutable_state():
    first = build_jev_request("system", "user", "jev-test")
    second = build_jev_request("system", "user", "jev-test")
    assert first == second
    questions = first["questions"]
    assert set(questions) == {"direction", "bullish_strength", "bearish_strength"}
    assert questions["direction"]["type"] == "choice"
    assert set(questions["direction"]["criteria"]) == {"bullish", "bearish", "neutral"}
    for question in questions.values():
        instructions = question["instructions"]
        for phrase in ("`investor_prompt`", "`financial_snapshot`", "evidence restrictions", "point-in-time", "response format, writing style, and generating a thesis"):
            assert phrase in instructions
    for direction in ("bullish", "bearish"):
        question = questions[f"{direction}_strength"]
        assert question["type"] == "score"
        assert f"{direction} investment case" in question["instructions"]
        assert "independently" in question["instructions"]
        assert "typed strength rubric governs" in question["instructions"]
        assert len(question["criteria"]) == 5

    questions["bullish_strength"]["criteria"][0] = "changed"
    questions["direction"]["criteria"].clear()
    assert questions["bearish_strength"]["criteria"] == second["questions"]["bearish_strength"]["criteria"]
    assert second == build_jev_request("system", "user", "jev-test")


@pytest.mark.parametrize(
    "direction,bullish,bearish,expected",
    [
        ("bullish", 3.2, 1.6, 80.0),
        ("bearish", 3.2, 1.6, 40.0),
        ("bullish", 1.23456789, 4, 30.86419725),
        ("bearish", 4, 1.23456789, 30.86419725),
        ("bullish", 4, 0, 100.0),
        ("bearish", 0, 4, 100.0),
        ("bullish", 0, 4, 0.0),
        ("bearish", 4, 0, 0.0),
        ("neutral", 4, 4, 0.0),
    ],
)
def test_mapping_and_existing_agent_parser(direction, bullish, bearish, expected, tmp_path):
    payload, _ = normalize_jev_response(_response(direction, bullish, bearish))
    assert payload["signal"] == direction
    assert payload["confidence"] == pytest.approx(expected)
    assert set(payload) == {"signal", "confidence", "reasoning"}
    agent = BuffettAgent(llm=NoNetworkLLM(), cache=PromptCache(tmp_path))
    assert agent._parse(json.dumps(payload)) == payload


@pytest.mark.parametrize(
    "direction,expected",
    [
        ("bullish", "Bullish assessment; investment conviction 80/100. No written thesis generated."),
        ("bearish", "Bearish assessment; investment conviction 40/100. No written thesis generated."),
        ("neutral", "Neutral assessment; directional investment conviction 0/100. No written thesis generated."),
    ],
)
def test_summary_is_templated_from_outputs(direction, expected):
    payload, _ = normalize_jev_response(_response(direction))
    assert payload["reasoning"] == expected


@pytest.mark.parametrize("direction", ["bullish", "bearish", "neutral"])
def test_native_confidence_does_not_scale_or_gate_conviction(direction):
    response = _response(direction)
    baseline, _ = normalize_jev_response(response)
    for confidence in (0, 0.01, 1):
        for answer in response["answers"].values():
            answer["confidence"] = confidence
        payload, metadata = normalize_jev_response(response)
        assert payload == baseline
        assert all(answer["confidence"] == confidence for answer in metadata["response"]["answers"].values())


def test_native_response_is_preserved_without_aliasing_or_mutation():
    response = _response()
    response["future_field"] = {"nested": [1, 2]}
    response["answers"]["direction"]["future_field"] = "keep"
    response["answers"]["extra_answer"] = {"type": "noul", "noul": 0.7}
    original = deepcopy(response)
    _, metadata = normalize_jev_response(response)
    assert response == original
    assert metadata == {"contract_version": JEV_CONTRACT_VERSION, "response": original}
    response["answers"]["bullish_strength"]["score"] = 0
    response["future_field"]["nested"].append(3)
    assert metadata["response"] == original


@pytest.mark.parametrize("response", [None, [], "invalid", {}, {"answers": None}, {"answers": []}])
def test_invalid_response_envelopes_raise_contract_error(response):
    with pytest.raises(JevContractError):
        normalize_jev_response(response)


@pytest.mark.parametrize("name", ["direction", "bullish_strength", "bearish_strength"])
@pytest.mark.parametrize("problem", ["missing", "not-object", "wrong-type", "missing-confidence", "missing-probabilities"])
def test_all_three_answers_are_required_even_for_neutral(name, problem):
    response = _response("neutral")
    if problem == "missing":
        del response["answers"][name]
    elif problem == "not-object":
        response["answers"][name] = []
    elif problem == "wrong-type":
        response["answers"][name]["type"] = "noul"
    else:
        del response["answers"][name][problem.removeprefix("missing-")]
    with pytest.raises(JevContractError, match=name):
        normalize_jev_response(response)


@pytest.mark.parametrize("choice", [None, "buy", "BULLISH", [], True])
def test_invalid_choices_raise_contract_error(choice):
    response = _response()
    response["answers"]["direction"]["choice"] = choice
    with pytest.raises(JevContractError, match="direction.choice"):
        normalize_jev_response(response)


@pytest.mark.parametrize(
    "name,field,upper",
    [
        ("direction", "confidence", 1),
        ("bullish_strength", "confidence", 1),
        ("bearish_strength", "confidence", 1),
        ("bullish_strength", "score", 4),
        ("bearish_strength", "score", 4),
    ],
)
@pytest.mark.parametrize("invalid", [None, True, False, "0.5", float("nan"), float("inf"), -float("inf"), -0.01, "above-bound"])
def test_invalid_numbers_raise_contract_error(name, field, upper, invalid):
    response = _response()
    response["answers"][name][field] = upper + 0.01 if invalid == "above-bound" else invalid
    with pytest.raises(JevContractError, match=f"{name}.{field}"):
        normalize_jev_response(response)


@pytest.mark.parametrize("name", ["direction", "bullish_strength", "bearish_strength"])
@pytest.mark.parametrize("problem", ["missing-key", "extra-key", "wrong-keys", "wrong-total", "not-object", "boolean", "non-finite", "negative", "above-one", "string"])
def test_invalid_distributions_raise_contract_error(name, problem):
    response = _response()
    probabilities = response["answers"][name]["probabilities"]
    key = next(iter(probabilities))
    if problem == "missing-key":
        del probabilities[key]
    elif problem == "extra-key":
        probabilities["unexpected"] = 0
    elif problem == "wrong-keys":
        probabilities[99] = probabilities.pop(key)
    elif problem == "wrong-total":
        probabilities.update(dict.fromkeys(probabilities, 0.0))
    elif problem == "not-object":
        response["answers"][name]["probabilities"] = []
    else:
        probabilities[key] = {"boolean": True, "non-finite": float("nan"), "negative": -0.1, "above-one": 1.1, "string": "0.5"}[problem]
    with pytest.raises(JevContractError, match=f"{name}.probabilities"):
        normalize_jev_response(response)


@pytest.mark.parametrize("offset,accepted", [(0.0009, True), (-0.0009, True), (0.0011, False), (-0.0011, False)])
def test_distribution_total_tolerance(offset, accepted):
    response = _response()
    response["answers"]["direction"]["probabilities"]["neutral"] += offset
    if accepted:
        normalize_jev_response(response)
    else:
        with pytest.raises(JevContractError):
            normalize_jev_response(response)
