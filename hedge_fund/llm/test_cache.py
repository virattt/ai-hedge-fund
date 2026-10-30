"""Prompt cache identities preserve the boundaries between input fields."""

import pytest

from hedge_fund.llm.cache import PromptCache, prompt_key


@pytest.mark.parametrize(
    "first,second",
    [
        (("agent|model", "id", "system", "user"), ("agent", "model|id", "system", "user")),
        (("agent", "model|system", "prompt", "user"), ("agent", "model", "system|prompt", "user")),
        (("agent", "model", "system|prompt", "user"), ("agent", "model", "system", "prompt|user")),
        (("agent", "model", "|", ""), ("agent", "model", "", "|")),
    ],
)
def test_prompt_key_preserves_field_boundaries(first, second):
    assert prompt_key(*first) != prompt_key(*second)


@pytest.mark.parametrize(
    "fields",
    [
        ("agent", "model", "system", "user"),
        ("agent", "model", 'system|"quoted"\n', "user\\path"),
        ("", "", "", ""),
    ],
)
def test_prompt_key_is_stable_and_keeps_its_format(fields):
    key = prompt_key(*fields)
    assert key == prompt_key(*fields)
    assert len(key) == 24
    assert all(character in "0123456789abcdef" for character in key)


def test_prompt_cache_keeps_delimited_prompts_separate(tmp_path):
    cache = PromptCache(tmp_path)
    first = prompt_key("agent", "model", "system|prompt", "user")
    second = prompt_key("agent", "model", "system", "prompt|user")

    cache.put(first, {"parsed": {"reasoning": "first response"}})
    assert cache.get(second) is None

    cache.put(second, {"parsed": {"reasoning": "second response"}})
    assert cache.get(first)["parsed"]["reasoning"] == "first response"
    assert cache.get(second)["parsed"]["reasoning"] == "second response"
