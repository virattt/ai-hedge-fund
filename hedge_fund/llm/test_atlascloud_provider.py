"""Atlas Cloud registry and OpenAI-compatible client coverage."""

from __future__ import annotations

import sys
import types

import pytest

from hedge_fund.llm import (
    env_var_for,
    load_api_models,
    make_llm,
    provider_for,
    SUPPORTED_PROVIDERS,
)

QWEN_MODEL = "qwen/qwen3.5-flash"
DEEPSEEK_MODEL = "deepseek-ai/deepseek-v4-pro"


@pytest.fixture(autouse=True)
def clean_atlascloud_env(monkeypatch):
    monkeypatch.delenv("ATLASCLOUD_API_KEY", raising=False)
    monkeypatch.delenv("ATLASCLOUD_API_BASE", raising=False)


def install_fake_openai(monkeypatch, captured):
    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    module = types.ModuleType("langchain_openai")
    module.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "langchain_openai", module)
    return FakeChatOpenAI


def test_atlascloud_models_are_registered():
    atlas_models = {(display_name, model_id, provider) for display_name, model_id, provider in load_api_models() if provider == "Atlas Cloud"}

    assert (
        "Atlas Cloud Qwen 3.5 Flash",
        QWEN_MODEL,
        "Atlas Cloud",
    ) in atlas_models
    assert (
        "Atlas Cloud DeepSeek V4 Pro",
        DEEPSEEK_MODEL,
        "Atlas Cloud",
    ) in atlas_models


def test_atlascloud_provider_is_supported():
    assert provider_for(QWEN_MODEL) == "Atlas Cloud"
    assert env_var_for("Atlas Cloud") == "ATLASCLOUD_API_KEY"
    assert "Atlas Cloud" in SUPPORTED_PROVIDERS


def test_atlascloud_uses_openai_compatible_endpoint(monkeypatch):
    captured = {}
    fake_chat = install_fake_openai(monkeypatch, captured)
    monkeypatch.setenv("ATLASCLOUD_API_KEY", "test-atlas-key")

    llm = make_llm(QWEN_MODEL)

    assert isinstance(llm._chat, fake_chat)
    assert captured == {
        "model": QWEN_MODEL,
        "api_key": "test-atlas-key",
        "timeout": 60.0,
        "max_retries": 1,
        "base_url": "https://api.atlascloud.ai/v1",
    }


def test_atlascloud_allows_base_url_override(monkeypatch):
    captured = {}
    install_fake_openai(monkeypatch, captured)
    monkeypatch.setenv("ATLASCLOUD_API_KEY", "test-atlas-key")
    monkeypatch.setenv("ATLASCLOUD_API_BASE", "https://atlas.example/v1")

    make_llm(DEEPSEEK_MODEL)

    assert captured["base_url"] == "https://atlas.example/v1"


def test_atlascloud_requires_api_key():
    with pytest.raises(ValueError, match="ATLASCLOUD_API_KEY"):
        make_llm(QWEN_MODEL)
