import json
import sys
import types
from pathlib import Path

import pytest


def _install_provider_stub(module_name: str, class_name: str):
    module = types.ModuleType(module_name)
    setattr(module, class_name, type(class_name, (), {}))
    sys.modules.setdefault(module_name, module)


_install_provider_stub("langchain_anthropic", "ChatAnthropic")
_install_provider_stub("langchain_deepseek", "ChatDeepSeek")
_install_provider_stub("langchain_google_genai", "ChatGoogleGenerativeAI")
_install_provider_stub("langchain_groq", "ChatGroq")
_install_provider_stub("langchain_xai", "ChatXAI")
_install_provider_stub("langchain_gigachat", "GigaChat")
_install_provider_stub("langchain_ollama", "ChatOllama")

langchain_openai = types.ModuleType("langchain_openai")
langchain_openai.ChatOpenAI = type("ChatOpenAI", (), {})
langchain_openai.AzureChatOpenAI = type("AzureChatOpenAI", (), {})
sys.modules.setdefault("langchain_openai", langchain_openai)

from src.llm import models
from src.llm.models import ModelProvider, get_model, get_model_info


def test_atlascloud_models_are_registered():
    model_path = Path(models.__file__).with_name("api_models.json")
    registered_models = json.loads(model_path.read_text())

    atlas_models = [model for model in registered_models if model["provider"] == ModelProvider.ATLASCLOUD.value]

    assert {
        "display_name": "Atlas Cloud Qwen 3.5 Flash",
        "model_name": "qwen/qwen3.5-flash",
        "provider": "Atlas Cloud",
    } in atlas_models
    assert {
        "display_name": "Atlas Cloud DeepSeek V4 Pro",
        "model_name": "deepseek-ai/deepseek-v4-pro",
        "provider": "Atlas Cloud",
    } in atlas_models


def test_get_model_info_finds_atlascloud_models():
    model_info = get_model_info("qwen/qwen3.5-flash", ModelProvider.ATLASCLOUD)

    assert model_info is not None
    assert model_info.provider == ModelProvider.ATLASCLOUD


def test_atlascloud_uses_openai_compatible_endpoint(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(models, "ChatOpenAI", FakeChatOpenAI)

    llm = get_model(
        "qwen/qwen3.5-flash",
        ModelProvider.ATLASCLOUD,
        {"ATLASCLOUD_API_KEY": "test-atlas-key"},
    )

    assert isinstance(llm, FakeChatOpenAI)
    assert captured == {
        "model": "qwen/qwen3.5-flash",
        "api_key": "test-atlas-key",
        "base_url": "https://api.atlascloud.ai/v1",
    }


def test_atlascloud_allows_base_url_override(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(models, "ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setenv("ATLASCLOUD_API_BASE", "https://atlas.example/v1")

    get_model(
        "deepseek-ai/deepseek-v4-pro",
        ModelProvider.ATLASCLOUD,
        {"ATLASCLOUD_API_KEY": "test-atlas-key"},
    )

    assert captured["base_url"] == "https://atlas.example/v1"


def test_atlascloud_requires_api_key(monkeypatch):
    monkeypatch.delenv("ATLASCLOUD_API_KEY", raising=False)

    with pytest.raises(ValueError, match="Atlas Cloud API key not found"):
        get_model("qwen/qwen3.5-flash", ModelProvider.ATLASCLOUD, {})
