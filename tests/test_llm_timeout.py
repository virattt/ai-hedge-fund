import pytest

from src.llm.models import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ModelProvider,
    get_model,
)

# (provider, env vars required by get_model, attribute holding the timeout)
TIMEOUT_CASES = [
    (ModelProvider.OPENAI, {"OPENAI_API_KEY": "test"}, "request_timeout"),
    (ModelProvider.GROQ, {"GROQ_API_KEY": "test"}, "request_timeout"),
    (ModelProvider.ANTHROPIC, {"ANTHROPIC_API_KEY": "test"}, "default_request_timeout"),
    (ModelProvider.DEEPSEEK, {"DEEPSEEK_API_KEY": "test"}, "request_timeout"),
    (ModelProvider.GOOGLE, {"GOOGLE_API_KEY": "test"}, "timeout"),
    (ModelProvider.OPENROUTER, {"OPENROUTER_API_KEY": "test"}, "request_timeout"),
    (ModelProvider.KIMI, {"MOONSHOT_API_KEY": "test"}, "request_timeout"),
    (ModelProvider.XAI, {"XAI_API_KEY": "test"}, "request_timeout"),
    (ModelProvider.GIGACHAT, {"GIGACHAT_API_KEY": "test"}, "timeout"),
]


@pytest.mark.parametrize("provider,env,attr", TIMEOUT_CASES)
def test_get_model_sets_request_timeout(provider, env, attr, monkeypatch):
    """Every provider gets a request timeout so a hung API call cannot block
    an analysis task forever (the retry loop in call_llm never runs if the
    first invoke hangs)."""
    monkeypatch.delenv("GIGACHAT_USER", raising=False)
    monkeypatch.delenv("GIGACHAT_PASSWORD", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    model = get_model("test-model", provider)

    assert getattr(model, attr) == DEFAULT_REQUEST_TIMEOUT_SECONDS


def test_ollama_client_gets_timeout(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    model = get_model("test-model", ModelProvider.OLLAMA)
    assert model.client_kwargs["timeout"] == DEFAULT_REQUEST_TIMEOUT_SECONDS


def test_azure_openai_gets_timeout(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "test-deployment")

    model = get_model("test-model", ModelProvider.AZURE_OPENAI)

    assert model.request_timeout == DEFAULT_REQUEST_TIMEOUT_SECONDS
