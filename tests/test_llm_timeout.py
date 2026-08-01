import time
import sys
import types

from pydantic import BaseModel


def install_optional_dependency_stubs():
    provider_classes = {
        "langchain_anthropic": ["ChatAnthropic"],
        "langchain_deepseek": ["ChatDeepSeek"],
        "langchain_google_genai": ["ChatGoogleGenerativeAI"],
        "langchain_groq": ["ChatGroq"],
        "langchain_xai": ["ChatXAI"],
        "langchain_openai": ["ChatOpenAI", "AzureChatOpenAI"],
        "langchain_gigachat": ["GigaChat"],
        "langchain_ollama": ["ChatOllama"],
    }
    for module_name, class_names in provider_classes.items():
        if module_name not in sys.modules:
            module = types.ModuleType(module_name)
            for class_name in class_names:
                setattr(module, class_name, type(class_name, (), {}))
            sys.modules[module_name] = module

    if "langchain_core" not in sys.modules:
        sys.modules["langchain_core"] = types.ModuleType("langchain_core")
    if "langchain_core.messages" not in sys.modules:
        messages = types.ModuleType("langchain_core.messages")
        messages.BaseMessage = type("BaseMessage", (), {})
        sys.modules["langchain_core.messages"] = messages


install_optional_dependency_stubs()

from src.utils import llm as llm_utils


class DummyResponse(BaseModel):
    decision: str


class FakeModelInfo:
    def has_json_mode(self):
        return True


class FakeLLM:
    def __init__(self, invoke_func):
        self.invoke_func = invoke_func

    def with_structured_output(self, *_args, **_kwargs):
        return self

    def invoke(self, prompt):
        return self.invoke_func(prompt)


def install_fake_model(monkeypatch, invoke_func):
    monkeypatch.setattr(llm_utils, "get_model_info", lambda *_args, **_kwargs: FakeModelInfo())
    monkeypatch.setattr(llm_utils, "get_model", lambda *_args, **_kwargs: FakeLLM(invoke_func))


def test_call_llm_retries_after_timeout(monkeypatch):
    calls = 0

    def invoke(_prompt):
        nonlocal calls
        calls += 1
        if calls == 1:
            time.sleep(0.05)
            return DummyResponse(decision="late")
        return DummyResponse(decision="ok")

    install_fake_model(monkeypatch, invoke)

    result = llm_utils.call_llm("prompt", DummyResponse, max_retries=2, timeout=0.01)

    assert result == DummyResponse(decision="ok")
    assert calls == 2


def test_call_llm_uses_default_factory_after_timeout(monkeypatch):
    def invoke(_prompt):
        time.sleep(0.05)
        return DummyResponse(decision="late")

    install_fake_model(monkeypatch, invoke)

    started = time.monotonic()
    result = llm_utils.call_llm(
        "prompt",
        DummyResponse,
        max_retries=1,
        timeout=0.01,
        default_factory=lambda: DummyResponse(decision="fallback"),
    )

    assert result == DummyResponse(decision="fallback")
    assert time.monotonic() - started < 0.5
