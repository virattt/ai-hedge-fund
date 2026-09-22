"""Every provider must construct, and every response shape must flatten.

The constructor tests are the point: a wrong kwarg name for one provider is a
TypeError that would otherwise surface only mid-run, after minutes of warming.
Nothing here touches the network — building a langchain chat model does not
call the API.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import Mock

import pytest
import requests

from hedge_fund.data.client import FDClientError
from hedge_fund.llm import ChatLLM
from hedge_fund.llm import client as client_module
from hedge_fund.llm import contract
from hedge_fund.llm import (
    LLMCallError,
    LLMClient,
    env_var_for,
    load_api_models,
    make_llm,
    prompt_key,
    PromptCache,
    provider_for,
    SUPPORTED_PROVIDERS,
)
from hedge_fund.llm.client import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_TIMEOUT,
    OLLAMA_BASE_URL_VAR,
    OLLAMA_PLACEHOLDER_KEY,
    OPENAI_BASE_URL_VARS,
    TIMEOUT_ENV_VAR,
    _flatten,
    JevLLM,
    resolve_ollama_base_url,
    resolve_timeout,
)
from hedge_fund.llm.registry import KEYLESS_PROVIDERS, PROVIDER_ENV_VARS
from hedge_fund.llm.test_contract import _response
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, BuffettAgent, LLMAgent, MungerAgent
from hedge_fund.signals.test_llm_agents import (
    _history,
    BULLISH,
    FakeLLM,
    MockDataClient,
)

# One model id per provider, taken from the registry so this test fails loudly
# if a provider is dropped from api_models.json.
_BY_PROVIDER = {prov: mid for _, mid, prov in load_api_models()}


@pytest.fixture
def keyed(monkeypatch):
    """Every provider key present, so make_llm gets past its key check."""
    for env_var in PROVIDER_ENV_VARS.values():
        monkeypatch.setenv(env_var, "test-key-not-real")
    monkeypatch.delenv("HEDGE_FUND_LLM_MODEL", raising=False)
    for name in (*OPENAI_BASE_URL_VARS, TIMEOUT_ENV_VAR, OLLAMA_BASE_URL_VAR,
                 "MOONSHOT_BASE_URL", "DEEPSEEK_BASE_URL", "DEEPSEEK_API_BASE",
                 "XAI_BASE_URL", "XAI_API_BASE"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("provider", sorted(SUPPORTED_PROVIDERS))
def test_every_supported_provider_constructs(provider, keyed):
    """A supported provider builds a client with the model id it was given."""
    model_id = _BY_PROVIDER.get(provider)
    assert model_id, f"{provider} is supported but absent from the registry"
    llm = make_llm(model_id)
    assert llm.model == model_id
    assert hasattr(llm, "complete")


def test_registry_and_clients_agree():
    """Every provider in the registry is one we can actually reach — the
    picker greys out the rest, so a mismatch means a dead row or a broken run.
    """
    listed = {prov for _, _, prov in load_api_models()}
    assert listed <= SUPPORTED_PROVIDERS, f"no client for: {listed - SUPPORTED_PROVIDERS}"


def test_missing_key_names_the_variable(monkeypatch):
    """The error tells you which variable to set — the only actionable fact."""
    monkeypatch.delenv("HEDGE_FUND_LLM_MODEL", raising=False)
    for env_var in PROVIDER_ENV_VARS.values():
        monkeypatch.delenv(env_var, raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        make_llm("claude-opus-5")


def test_unlisted_model_falls_back_to_anthropic(keyed):
    """A model newer than the registry still runs, rather than needing a
    code change first."""
    llm = make_llm("claude-something-unreleased")
    assert llm.model == "claude-something-unreleased"
    assert type(llm._chat).__name__ == "ChatAnthropic"


def test_kimi_accepts_moonshot_key(monkeypatch):
    """v1 reads MOONSHOT_API_KEY first; the same .env must work here."""
    monkeypatch.delenv("HEDGE_FUND_LLM_MODEL", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key-not-real")
    assert make_llm(_BY_PROVIDER["Kimi"]).model == _BY_PROVIDER["Kimi"]


def test_provider_for_reads_the_registry():
    assert provider_for("claude-opus-5") == "Anthropic"
    assert provider_for("claude-fable-5-1") == "Anthropic"
    assert provider_for("gpt-5.6") == "OpenAI"
    assert provider_for("gpt-6-astra") == "OpenAI"
    assert provider_for("llama3.1") == "Ollama"
    assert provider_for("qwen2.5") == "Ollama"
    assert provider_for("not-a-model") is None


def test_ollama_is_keyless_and_supported():
    """The picker and missing_key() treat Ollama as selectable without a cloud key."""
    assert "Ollama" in KEYLESS_PROVIDERS
    assert "Ollama" in SUPPORTED_PROVIDERS
    assert "Ollama" not in PROVIDER_ENV_VARS
    assert env_var_for("Ollama") is None


class FakeChunk:
    def __init__(self, content) -> None:
        self.content = content


class FakeChat:
    """Records which path was taken, so a test can prove streaming happened."""

    def __init__(self, chunks: list) -> None:
        self._chunks = chunks
        self.streamed = False
        self.invoked = False

    def invoke(self, messages):
        self.invoked = True
        return FakeChunk("".join(
            c.content if isinstance(c.content, str) else "" for c in self._chunks))

    def stream(self, messages):
        self.streamed = True
        yield from self._chunks


class TestStreaming:
    """A listener changes how the text arrives, never what comes back — the
    prompt cache and the parse must not be able to tell the difference.
    """

    def test_no_listener_does_not_stream(self):
        chat = FakeChat([FakeChunk("done")])
        assert ChatLLM("m", chat).complete("s", "u") == "done"
        assert chat.invoked and not chat.streamed

    def test_listener_sees_every_piece_and_the_return_is_whole(self):
        chat = FakeChat([FakeChunk('{"sig'), FakeChunk('nal": '), FakeChunk('"buy"}')])
        seen: list[str] = []
        result = ChatLLM("m", chat, seen.append).complete("s", "u")
        assert chat.streamed
        assert seen == ['{"sig', 'nal": ', '"buy"}']
        assert result == '{"signal": "buy"}'

    def test_chunk_blocks_join_without_a_separator(self):
        """Whole-message blocks join on a newline; stream blocks are fragments
        of one continuing string, and a newline would land mid-word."""
        chat = FakeChat([FakeChunk([{"type": "text", "text": "mo"},
                                    {"type": "text", "text": "at"}])])
        assert ChatLLM("m", chat, lambda _: None).complete("s", "u") == "moat"

    def test_thinking_chunks_reach_neither_the_listener_nor_the_result(self):
        chat = FakeChat([
            FakeChunk([{"type": "thinking", "thinking": "weighing margins"}]),
            FakeChunk([{"type": "text", "text": "verdict"}]),
        ])
        seen: list[str] = []
        assert ChatLLM("m", chat, seen.append).complete("s", "u") == "verdict"
        assert seen == ["verdict"]

    def test_make_llm_passes_the_listener_through(self, keyed):
        """The TUI builds its agents with make_llm(on_token=...), so the
        listener has to survive the factory."""
        def listener(text: str) -> None:
            pass

        assert make_llm("claude-opus-5", on_token=listener)._on_token is listener


class TestFlatten:
    """Response shapes, matching v1's extract_json_from_response."""

    def test_plain_string_passes_through(self):
        assert _flatten('{"signal": "bullish"}') == '{"signal": "bullish"}'

    def test_text_blocks_are_joined(self):
        blocks = [{"type": "text", "text": '{"a":'}, {"type": "text", "text": ' 1}'}]
        assert _flatten(blocks) == '{"a":\n 1}'

    def test_thinking_blocks_are_dropped(self):
        """The whole reason this exists: a reasoning block stringified into
        the payload is prose in front of the JSON, and the parse fails."""
        blocks = [
            {"type": "thinking", "thinking": "Let me weigh the margins..."},
            {"type": "text", "text": '{"signal": "bearish"}'},
        ]
        assert _flatten(blocks) == '{"signal": "bearish"}'

    def test_bare_strings_in_a_list_are_kept(self):
        assert _flatten(["a", "b"]) == "a\nb"

    def test_unknown_block_types_are_dropped_not_stringified(self):
        blocks = [{"type": "tool_use", "id": "x"}, {"type": "text", "text": "ok"}]
        assert _flatten(blocks) == "ok"

    def test_none_becomes_empty(self):
        assert _flatten(None) == ""


class _StatusError(Exception):
    """Mimic provider HTTP errors without importing every SDK exception type."""

    def __init__(self, status, message=""):
        super().__init__(message)
        self.status_code = status


class TestTimeoutAndBaseUrl:
    """Timeout and OpenAI-compatible base URL contract: wiring plus mocked failures.

    Nothing here waits on a real socket. A dead endpoint is represented by a
    timeout/connection error that would hang only if the client omitted a timeout
    or swallowed the failure.
    """

    def test_resolve_timeout_prefers_argument_then_env_then_default(self, monkeypatch):
        monkeypatch.delenv(TIMEOUT_ENV_VAR, raising=False)
        assert resolve_timeout(None) == DEFAULT_TIMEOUT
        assert resolve_timeout(12) == 12.0
        monkeypatch.setenv(TIMEOUT_ENV_VAR, "8.5")
        assert resolve_timeout(None) == 8.5
        assert resolve_timeout(2) == 2.0

    @pytest.mark.parametrize("raw", ["0", "-1", "nan", "inf"])
    def test_resolve_timeout_rejects_non_positive_env(self, raw, monkeypatch):
        monkeypatch.setenv(TIMEOUT_ENV_VAR, raw)
        with pytest.raises(ValueError, match=TIMEOUT_ENV_VAR):
            resolve_timeout(None)

    def test_resolve_timeout_rejects_unparseable_env(self, monkeypatch):
        monkeypatch.setenv(TIMEOUT_ENV_VAR, "nope")
        with pytest.raises(ValueError, match=TIMEOUT_ENV_VAR):
            resolve_timeout(None)

    def test_blank_timeout_env_uses_default(self, monkeypatch):
        monkeypatch.setenv(TIMEOUT_ENV_VAR, "  ")
        assert resolve_timeout(None) == DEFAULT_TIMEOUT

    def test_openai_timeout_and_base_url_land_on_the_chat_model(self, keyed, monkeypatch):
        monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
        llm = make_llm("gpt-5.6", timeout=3.25)
        assert llm._timeout == 3.25
        assert llm._chat.request_timeout == 3.25
        assert llm._chat.openai_api_base == "https://example.invalid/v1"

    def test_openai_base_url_wins_over_api_base_alias(self, keyed, monkeypatch):
        monkeypatch.setenv("OPENAI_BASE_URL", "https://preferred.example/v1")
        monkeypatch.setenv("OPENAI_API_BASE", "https://legacy.example/v1")
        llm = make_llm("gpt-5.6")
        assert llm._chat.openai_api_base == "https://preferred.example/v1"

    def test_openai_api_base_alias_is_honored(self, keyed, monkeypatch):
        monkeypatch.setenv("OPENAI_API_BASE", "https://legacy.example/v1")
        llm = make_llm("gpt-5.6")
        assert llm._chat.openai_api_base == "https://legacy.example/v1"

    def test_openai_omits_base_url_when_unset(self, keyed):
        llm = make_llm("gpt-5.6")
        assert llm._chat.openai_api_base is None

    def test_timeout_env_used_when_make_llm_omits_timeout(self, keyed, monkeypatch):
        monkeypatch.setenv(TIMEOUT_ENV_VAR, "8")
        llm = make_llm("gpt-5.6")
        assert llm._chat.request_timeout == 8.0
        assert make_llm("gpt-5.6", timeout=2)._chat.request_timeout == 2.0

    def test_unlisted_model_uses_openai_when_base_url_is_set(self, keyed, monkeypatch):
        """Custom endpoints need the OpenAI wire format for unlisted ids
        (Groq, local proxies). Without a base URL they still fall back to Anthropic."""
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
        llm = make_llm("llama-3.3-70b-versatile")
        assert llm.model == "llama-3.3-70b-versatile"
        assert type(llm._chat).__name__ == "ChatOpenAI"
        assert llm._chat.openai_api_base == "https://api.groq.com/openai/v1"

    def test_kimi_honors_moonshot_base_url(self, keyed, monkeypatch):
        monkeypatch.setenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
        llm = make_llm(_BY_PROVIDER["Kimi"])
        assert llm._chat.openai_api_base == "https://api.moonshot.cn/v1"

    def test_deepseek_and_xai_honor_their_base_url_aliases(self, keyed, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://deepseek.example/v1")
        monkeypatch.setenv("XAI_API_BASE", "https://xai.example/v1")
        deepseek = make_llm(_BY_PROVIDER["DeepSeek"])
        xai = make_llm(_BY_PROVIDER["xAI"])
        assert deepseek._chat.api_base == "https://deepseek.example/v1"
        assert xai._chat.xai_api_base == "https://xai.example/v1"

    @pytest.mark.parametrize("provider", sorted(p for p in SUPPORTED_PROVIDERS if p != "TypeSafe"))
    def test_every_chat_provider_receives_timeout(self, provider, keyed):
        llm = make_llm(_BY_PROVIDER[provider], timeout=9)
        chat = llm._chat
        observed = getattr(chat, "request_timeout", None)
        if observed is None:
            observed = getattr(chat, "timeout", None)
        if observed is None:
            observed = getattr(chat, "default_request_timeout", None)
        assert observed == 9

    def test_dead_endpoint_fails_with_timeout_error_and_does_not_hang(self):
        class DeadChat:
            def invoke(self, messages):
                raise TimeoutError("The read operation timed out")

            def stream(self, messages):
                raise TimeoutError("The read operation timed out")

        with pytest.raises(LLMCallError, match="timed out") as caught:
            ChatLLM("gpt-5.6", DeadChat(), timeout=0.05).complete("s", "u")
        assert "timed out" in str(caught.value)
        assert "sk-" not in str(caught.value)

    def test_rejected_key_is_a_clear_error_without_leaking_secrets(self):
        chat = Mock()
        chat.invoke.side_effect = _StatusError(401, "Authorization: Bearer sk-secret")
        with pytest.raises(LLMCallError, match="rejected the API key") as caught:
            ChatLLM("gpt-5.6", chat).complete("s", "u")
        assert "sk-secret" not in str(caught.value)

    def test_rejected_model_is_a_clear_error(self):
        chat = Mock()
        chat.invoke.side_effect = Exception(
            "Error code: 404 - {'error': {'message': 'The model `llama-3.3-70b-versatile` does not exist'}}"
        )
        with pytest.raises(LLMCallError, match="rejected model gpt-5.6"):
            ChatLLM("gpt-5.6", chat).complete("s", "u")

    def test_connection_error_is_clear(self):
        chat = Mock()
        chat.invoke.side_effect = requests.ConnectionError("failed to connect")
        with pytest.raises(LLMCallError, match="connection error"):
            ChatLLM("gpt-5.6", chat).complete("s", "u")


class TestOllama:
    """Local, keyless Ollama: routing, OLLAMA_BASE_URL, fail-loud timeouts.

    Nothing here talks to a real daemon. Construction is local; complete()
    failures are injected on the chat model the way a missing Ollama host
    would surface (timeout / connection error).
    """

    def test_registry_model_constructs_without_any_cloud_key(self, monkeypatch):
        for variable in (*PROVIDER_ENV_VARS.values(), "MOONSHOT_API_KEY",
                         "HEDGE_FUND_LLM_MODEL", OLLAMA_BASE_URL_VAR, *OPENAI_BASE_URL_VARS):
            monkeypatch.delenv(variable, raising=False)
        llm = make_llm("llama3.1", timeout=4)
        assert llm.model == "llama3.1"
        assert type(llm._chat).__name__ == "ChatOpenAI"
        assert llm._timeout == 4
        assert llm._chat.request_timeout == 4
        assert llm._chat.openai_api_base == f"{DEFAULT_OLLAMA_HOST}/v1"
        assert llm._chat.openai_api_key.get_secret_value() == OLLAMA_PLACEHOLDER_KEY
        assert DEFAULT_OLLAMA_HOST in (llm._unreachable_hint or "")

    def test_prefix_routes_unlisted_tags_and_strips_the_prefix(self, monkeypatch):
        monkeypatch.delenv(OLLAMA_BASE_URL_VAR, raising=False)
        llm = make_llm("ollama:mistral")
        assert llm.model == "mistral"
        assert type(llm._chat).__name__ == "ChatOpenAI"
        assert llm._chat.openai_api_base == f"{DEFAULT_OLLAMA_HOST}/v1"

    def test_empty_prefix_is_rejected(self):
        with pytest.raises(ValueError, match="ollama:<tag>"):
            make_llm("ollama:")

    def test_ollama_base_url_default_and_overrides(self, monkeypatch):
        monkeypatch.delenv(OLLAMA_BASE_URL_VAR, raising=False)
        assert resolve_ollama_base_url() == f"{DEFAULT_OLLAMA_HOST}/v1"
        assert resolve_ollama_base_url("http://ollama.example:11434") == "http://ollama.example:11434/v1"
        assert resolve_ollama_base_url("http://ollama.example:11434/v1/") == "http://ollama.example:11434/v1"
        monkeypatch.setenv(OLLAMA_BASE_URL_VAR, "http://gpu-box:11434")
        llm = make_llm("qwen2.5")
        assert llm._chat.openai_api_base == "http://gpu-box:11434/v1"
        assert "http://gpu-box:11434" in (llm._unreachable_hint or "")

    def test_timeout_env_lands_on_the_chat_model(self, monkeypatch):
        monkeypatch.delenv(OLLAMA_BASE_URL_VAR, raising=False)
        monkeypatch.setenv(TIMEOUT_ENV_VAR, "7")
        llm = make_llm("llama3.1")
        assert llm._chat.request_timeout == 7.0
        assert make_llm("llama3.1", timeout=2)._chat.request_timeout == 2.0

    def test_missing_daemon_is_a_clear_timeout_not_a_hang(self):
        class DeadOllama:
            def invoke(self, messages):
                raise TimeoutError("The read operation timed out")

            def stream(self, messages):
                raise TimeoutError("The read operation timed out")

        with pytest.raises(LLMCallError, match="timed out") as caught:
            ChatLLM(
                "llama3.1",
                DeadOllama(),
                timeout=0.05,
                unreachable_hint=f"Is the Ollama daemon running at {DEFAULT_OLLAMA_HOST}?",
            ).complete("s", "u")
        assert DEFAULT_OLLAMA_HOST in str(caught.value)
        assert "sk-" not in str(caught.value)

    def test_missing_daemon_connection_error_names_the_host(self):
        chat = Mock()
        chat.invoke.side_effect = requests.ConnectionError("failed to connect")
        with pytest.raises(LLMCallError, match="connection error") as caught:
            ChatLLM(
                "llama3.1",
                chat,
                unreachable_hint=f"Is the Ollama daemon running at {DEFAULT_OLLAMA_HOST}?",
            ).complete("s", "u")
        assert "Ollama daemon" in str(caught.value)
        assert DEFAULT_OLLAMA_HOST in str(caught.value)

    def test_environment_model_routes_without_cloud_keys(self, monkeypatch):
        for variable in (*PROVIDER_ENV_VARS.values(), "MOONSHOT_API_KEY"):
            monkeypatch.delenv(variable, raising=False)
        monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "ollama:phi3")
        llm = make_llm()
        assert llm.model == "phi3"
        assert type(llm._chat).__name__ == "ChatOpenAI"


# Jev native transport and shared-agent integration.

API_KEY = "test-typesafe-secret-key"


@pytest.mark.parametrize("use_environment", [False, True])
def test_factory_routes_jev_with_only_its_key(use_environment, monkeypatch, http):
    for variable in (*PROVIDER_ENV_VARS.values(), "MOONSHOT_API_KEY", "HEDGE_FUND_LLM_MODEL"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", API_KEY)
    # If routing regresses, fail at chat construction rather than making a call.
    import langchain_anthropic
    import langchain_openai
    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", Mock(side_effect=AssertionError("chat construction")))
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", Mock(side_effect=AssertionError("chat construction")))
    if use_environment:
        monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "jev-1.13.0")
    listener = Mock()
    llm = make_llm(None if use_environment else "jev-1.13.0", timeout=17, max_tokens=1, on_token=listener)
    assert isinstance(llm, JevLLM)
    assert provider_for(llm.model) == "TypeSafe"
    assert ("Jev", "jev-1.13.0", "TypeSafe") in load_api_models()
    _serve(http, _http_response())
    llm.complete("investor", "snapshot")
    assert http[0].call_args.kwargs["timeout"] == 17
    assert "max_tokens" not in http[0].call_args.kwargs["json"]
    listener.assert_not_called()


def test_factory_missing_jev_key_names_variable(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        make_llm("jev-1.13.0")


def test_cli_jev_cycle_and_saved_replay(tmp_path, monkeypatch, http, capsys):
    import sys
    from hedge_fund import run
    from hedge_fund.data.models import Price
    from hedge_fund.pipeline.models import CycleRecord
    from hedge_fund.signals import llm_agent
    from hedge_fund.tui import keys

    class FinancialFixtures(MockDataClient):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get_prices(self, ticker, start_date, end_date, **kwargs):
            return [Price(open=100, high=100, low=100, close=100,
                          volume=1000, time=f"{end_date}T00:00:00Z")]

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(keys, "ENV_PATH", tmp_path / "saved.env")
    for variable in (*PROVIDER_ENV_VARS.values(), "MOONSHOT_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", API_KEY)
    monkeypatch.setenv("HEDGE_FUND_LLM_MODEL", "claude-opus-5")
    monkeypatch.setattr(run, "ensure_mandates_dir", lambda: tmp_path)
    monkeypatch.setattr(run, "FDClient", lambda: FinancialFixtures(metrics=_history()))
    monkeypatch.setattr(run, "CachedDataClient", lambda raw: raw)
    monkeypatch.setattr(llm_agent, "PromptCache", lambda: PromptCache(tmp_path / "llm"))
    mandate = tmp_path / "fund.yaml"
    mandate.write_text("""name: jev-test
strategies:
  - name: value
    models:
      - name: buffett
risk:
  max_position_pct: 0.25
  max_gross_exposure: 1.0
capital: 100000
""")
    output = tmp_path / "record.json"
    monkeypatch.setattr(sys, "argv", ["aihf", str(mandate), "--tickers", "AAPL,MSFT",
                                     "--date", "2025-01-15", "--model", "jev-1.13.0", "--out", str(output)])
    _serve(http, _http_response(), _http_response(_response("bearish")))
    run.main()
    first = CycleRecord.model_validate_json(output.read_text())
    assert CycleRecord.model_validate_json(capsys.readouterr().out) == first
    assert first.strategies[0].convictions == {"AAPL": 0.8, "MSFT": -0.4}
    assert first.positions["AAPL"] > 0 > first.positions["MSFT"]
    assert first.orders and first.fills and first.clamps
    assert all(abs(weight) <= 0.25 for weight in first.final_weights.values())
    assert http[0].call_count == 2
    run.main()
    second = CycleRecord.model_validate_json(output.read_text())
    capsys.readouterr()
    assert second.final_weights == first.final_weights
    assert second.positions == first.positions
    for before, after in zip(first.strategies[0].signals, second.strategies[0].signals):
        assert after.metadata["cached"] is True
        assert before.metadata["provider_metadata"] == after.metadata["provider_metadata"]
        assert after.metadata["provider_metadata"]["jev"]["response"]["answers"]
    assert http[0].call_count == 2


def _http_response(body=None, status=200, raw=None, retry_after=None):
    response = requests.Response()
    response.status_code = status
    response.encoding = "utf-8"
    response._content = (raw if raw is not None else json.dumps(body if body is not None else _response())).encode()
    response._content_consumed = True
    if retry_after is not None:
        response.headers["Retry-After"] = retry_after
    return response


@pytest.fixture
def http(monkeypatch):
    post = Mock(side_effect=AssertionError("Unexpected HTTP call"))
    sleep = Mock()
    monkeypatch.setattr(client_module.requests, "post", post)
    monkeypatch.setattr(client_module.time, "sleep", sleep)
    return post, sleep


def _serve(http, *responses):
    http[0].side_effect = list(responses)


def _agent(tmp_path, persona=BuffettAgent):
    return persona(llm=JevLLM(API_KEY), cache=PromptCache(tmp_path))


def test_native_request_and_auditable_compatibility_response(http):
    raw = json.dumps(_response(), indent=2) + "\n"
    _serve(http, _http_response(raw=raw))
    llm = JevLLM(API_KEY, timeout=12)
    assert isinstance(llm, LLMClient)
    payload = json.loads(llm.complete(" investor prompt\n", "financial snapshot\n"))
    request = contract.build_jev_request(" investor prompt\n", "financial snapshot\n", "jev-1.13.0")
    http[0].assert_called_once_with(
        JevLLM.ENDPOINT,
        json=request,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=12,
        allow_redirects=False,
    )
    http[1].assert_not_called()
    assert payload["signal"] == "bullish" and payload["confidence"] == 80
    assert "No written thesis generated" in payload["reasoning"]
    metadata = payload["provider_metadata"]["jev"]
    assert metadata["request"] == request
    assert metadata["response"] == _response()
    assert metadata["raw_response"] == raw
    assert metadata["contract_version"] == contract.JEV_CONTRACT_VERSION
    assert metadata["attempt_count"] == 1 and metadata["status_code"] == 200
    assert metadata["elapsed_seconds"] >= 0
    assert llm.model == "jev-1.13.0"
    assert API_KEY not in json.dumps(payload)


@pytest.mark.parametrize("key", [None, "", " \t\n"])
def test_empty_key_is_rejected(key, http):
    with pytest.raises(ValueError, match="non-empty TypeSafe API key"):
        JevLLM(key)
    http[0].assert_not_called()


@pytest.mark.parametrize("timeout", [0, -1, True, float("inf"), float("nan")])
def test_timeout_is_bounded(timeout):
    with pytest.raises(ValueError, match="timeout"):
        JevLLM(API_KEY, timeout=timeout)


def test_jev_dead_endpoint_uses_timeout_and_does_not_hang(http):
    """A silent TypeSafe host must raise inside the request timeout, not block."""
    _serve(http, requests.Timeout("dead endpoint"))
    with pytest.raises(LLMCallError) as caught:
        JevLLM(API_KEY, timeout=0.01).complete("s", "u")
    assert caught.value.diagnostic_record["failure_category"] == "transport"
    assert http[0].call_args.kwargs["timeout"] == 0.01
    http[0].assert_called_once()
    http[1].assert_not_called()


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504, 529])
def test_transient_http_failure_retries_once(status, http):
    _serve(http, _http_response(status=status), _http_response())
    payload = json.loads(JevLLM(API_KEY).complete("s", "u"))
    assert http[0].call_count == 2
    http[1].assert_called_once_with(1.0)
    assert http[0].call_args_list[0] == http[0].call_args_list[1]
    assert payload["provider_metadata"]["jev"]["attempt_count"] == 2


@pytest.mark.parametrize("header,delay", [("5", 5), ("0", 1), ("-2", 1), ("bad-date", 1), ("nan", 1), ("inf", 1)])
def test_retry_after_seconds_and_invalid_values(header, delay, http):
    _serve(http, _http_response(status=429, retry_after=header), _http_response())
    JevLLM(API_KEY).complete("s", "u")
    http[1].assert_called_once_with(delay)


def test_retry_after_http_date(monkeypatch, http):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock = Mock()
    clock.now.return_value = now
    monkeypatch.setattr(client_module, "datetime", clock)
    header = format_datetime(now + timedelta(seconds=10), usegmt=True)
    _serve(http, _http_response(status=529, retry_after=header), _http_response())
    JevLLM(API_KEY).complete("s", "u")
    http[1].assert_called_once_with(10)


def test_long_retry_after_fails_without_sleeping_or_retrying(http):
    _serve(http, _http_response(status=429, retry_after="61"))
    with pytest.raises(LLMCallError, match="retry delay exceeds timeout") as caught:
        JevLLM(API_KEY).complete("s", "u")
    assert caught.value.diagnostic_record["attempt_count"] == 1
    http[0].assert_called_once()
    http[1].assert_not_called()


@pytest.mark.parametrize("status,attempts", [(401, 1), (403, 1), (422, 1), (302, 1), (429, 2), (529, 2)])
def test_http_failures_have_bounded_attempts(status, attempts, http):
    _serve(http, *[_http_response(status=status, raw="failure") for _ in range(attempts)])
    with pytest.raises(LLMCallError, match=f"HTTP {status}") as caught:
        JevLLM(API_KEY).complete("s", "u")
    record = caught.value.diagnostic_record
    assert record["status_code"] == status
    assert record["raw_response"] == "failure"
    assert record["failure_category"] == "http"
    assert record["attempt_count"] == http[0].call_count == attempts
    assert http[1].call_count == attempts - 1


@pytest.mark.parametrize("exception", [requests.Timeout, requests.ConnectionError])
def test_network_failures_do_not_retry_or_leak_credentials(exception, http):
    _serve(http, exception(f"Authorization: Bearer {API_KEY}"))
    with pytest.raises(LLMCallError) as caught:
        JevLLM(API_KEY).complete("s", "u")
    assert caught.value.diagnostic_record["failure_category"] == "transport"
    assert caught.value.diagnostic_record["status_code"] is None
    assert caught.value.diagnostic_record["raw_response"] is None
    assert API_KEY not in str(caught.value)
    assert API_KEY not in json.dumps(caught.value.diagnostic_record)
    assert caught.value.__suppress_context__ is True
    http[0].assert_called_once()
    http[1].assert_not_called()


@pytest.mark.parametrize("raw,category", [("<html>bad gateway</html>", "json_decode"), ('{"answers": {}}', "contract")])
def test_invalid_success_response_is_not_retried(raw, category, http):
    _serve(http, _http_response(raw=raw))
    with pytest.raises(LLMCallError) as caught:
        JevLLM(API_KEY).complete("s", "u")
    record = caught.value.diagnostic_record
    assert record["raw_response"] == raw
    assert record["status_code"] == 200
    assert record["failure_category"] == category
    http[0].assert_called_once()
    http[1].assert_not_called()


def test_echoed_key_is_redacted_from_success_and_failure_metadata(http):
    native = _response()
    native["debug"] = {API_KEY: [API_KEY]}
    _serve(http, _http_response(native), _http_response(status=401, raw=f"Invalid key: {API_KEY}"))
    llm = JevLLM(API_KEY)
    result = llm.complete("s", "u")
    assert API_KEY not in result
    assert "[REDACTED]" in result
    with pytest.raises(LLMCallError) as caught:
        llm.complete("s", "u")
    assert caught.value.diagnostic_record["raw_response"] == "Invalid key: [REDACTED]"


@pytest.mark.parametrize("persona", [cls for cls in ALPHA_MODEL_REGISTRY.values() if issubclass(cls, LLMAgent)], ids=lambda cls: cls.__name__)
@pytest.mark.parametrize("direction,strength,expected", [("bullish", 3.2, 0.8), ("bearish", 1.6, -0.4), ("neutral", 4, 0), ("bullish", 0, 0), ("bearish", 0, 0)])
def test_every_agent_maps_and_replays_native_metadata(persona, direction, strength, expected, tmp_path, http):
    native = _response(direction, bullish=strength, bearish=strength)
    raw = json.dumps(native, indent=2)
    _serve(http, _http_response(raw=raw))
    agent = _agent(tmp_path, persona)
    data = MockDataClient(metrics=_history())
    first = agent.predict("TEST", "2025-01-15", data)
    # Use a fresh client/agent to prove replay does not depend on live state.
    second = _agent(tmp_path, persona).predict("TEST", "2025-02-20", data)
    assert first.value == second.value == pytest.approx(expected)
    assert second.date == "2025-02-20"
    assert first.metadata["signal"] == second.metadata["signal"] == direction
    assert first.metadata["abstained"] is second.metadata["abstained"] is False
    assert first.metadata["cached"] is False and second.metadata["cached"] is True
    assert first.metadata["provider_metadata"] == second.metadata["provider_metadata"]
    assert first.metadata["provider_metadata"]["jev"]["response"] == native
    record = PromptCache(tmp_path).get(first.metadata["prompt_key"])
    assert record["parsed"]["provider_metadata"] == first.metadata["provider_metadata"]
    assert record["system"] == agent.get_system_prompt()
    audit = record["parsed"]["provider_metadata"]["jev"]
    assert audit["raw_response"] == raw
    assert audit["request"]["state"] == {"investor_prompt": record["system"], "financial_snapshot": record["user"]}
    assert json.loads(record["response"])["provider_metadata"] == first.metadata["provider_metadata"]
    http[0].assert_called_once()


@pytest.mark.parametrize("change", ["snapshot", "persona", "model", "questions", "version"])
def test_changed_semantics_miss_cache(change, tmp_path, http, monkeypatch):
    _serve(http, _http_response(), _http_response())
    agent = _agent(tmp_path)
    data = MockDataClient(metrics=_history())
    first = agent.predict("TEST", "2025-01-15", data)
    if change == "snapshot":
        data = MockDataClient(metrics=_history(7))
    elif change == "persona":
        agent = _agent(tmp_path, MungerAgent)
    elif change == "model":
        agent._llm.model = "jev-another-version"
    elif change == "version":
        monkeypatch.setattr(contract, "JEV_CONTRACT_VERSION", contract.JEV_CONTRACT_VERSION + 1)
    else:
        build = contract.build_jev_request

        def changed(*args):
            request = build(*args)
            request["questions"]["bullish_strength"]["criteria"][0] += " Changed rubric."
            return request

        monkeypatch.setattr(contract, "build_jev_request", changed)
    second = agent.predict("TEST", "2025-01-15", data)
    assert second.metadata["cached"] is False
    assert first.metadata["prompt_key"] != second.metadata["prompt_key"]
    assert http[0].call_count == 2


def test_cache_identity_excludes_credentials_and_timeout_but_includes_agent_and_endpoint(monkeypatch):
    llm = JevLLM(API_KEY)
    baseline = llm.cache_key("buffett", "system", "user")
    assert baseline == JevLLM("other-secret", timeout=5).cache_key("buffett", "system", "user")
    assert baseline != llm.cache_key("munger", "system", "user")
    assert baseline != llm.cache_key("buffett", "changed system", "user")
    assert baseline != llm.cache_key("buffett", "system", "changed user")
    monkeypatch.setattr(llm, "ENDPOINT", "https://example.invalid/changed")
    assert baseline != llm.cache_key("buffett", "system", "user")


@pytest.mark.parametrize("failure", ["http", "transport", "json_decode", "contract"])
def test_failure_diagnostics_abstain_then_retry_successfully(failure, tmp_path, http, caplog):
    failed = {
        "http": _http_response(status=401, raw=f"Invalid key: {API_KEY}"),
        "transport": requests.Timeout(API_KEY),
        "json_decode": _http_response(raw="invalid json"),
        "contract": _http_response({"answers": {}}),
    }[failure]
    _serve(http, failed, _http_response())
    agent = _agent(tmp_path)
    data = MockDataClient(metrics=_history())
    first = agent.predict("TEST", "2025-01-15", data)
    assert first.value == 0 and first.metadata["abstained"] is True
    record = PromptCache(tmp_path).get(first.metadata["prompt_key"])
    assert "parsed" not in record
    assert record["diagnostics"]["failure_category"] == failure
    assert record["diagnostics"]["request"]["state"]["investor_prompt"] == agent.get_system_prompt()
    assert record["diagnostics"]["elapsed_seconds"] >= 0
    assert API_KEY not in json.dumps(record) + first.reasoning + caplog.text
    second = agent.predict("TEST", "2025-01-15", data)
    assert second.value == 0.8 and second.metadata["abstained"] is False
    assert second.metadata["cached"] is False
    assert second.metadata["prompt_key"] == first.metadata["prompt_key"]
    assert http[0].call_count == 2


def test_data_errors_propagate_and_insufficient_history_skips_http(tmp_path, http):
    agent = _agent(tmp_path)
    with pytest.raises(FDClientError):
        agent.predict("TEST", "2025-01-15", MockDataClient(error=FDClientError("offline")))
    signal = agent.predict("TEST", "2025-01-15", MockDataClient(metrics=[]))
    assert signal.metadata["abstained"] is True
    http[0].assert_not_called()


@pytest.mark.parametrize("flavor", ["fake", "chat"])
def test_legacy_clients_keep_keys_and_signal_shape(flavor, tmp_path):
    chat = Mock()
    chat.invoke.return_value.content = BULLISH
    llm = FakeLLM(BULLISH) if flavor == "fake" else ChatLLM("legacy-chat", chat)
    agent = BuffettAgent(llm=llm, cache=PromptCache(tmp_path))
    data = MockDataClient(metrics=_history())
    snapshot = agent.build_snapshot("TEST", "2025-01-15", data)
    key = prompt_key(agent.name, llm.model, agent.get_system_prompt(), agent.build_user_prompt(snapshot))
    first = agent.predict("TEST", "2025-01-15", data)
    second = agent.predict("TEST", "2025-01-15", data)
    assert first.value == second.value == 0.8
    assert first.metadata["prompt_key"] == key
    assert set(first.metadata) == {"signal", "confidence", "model", "prompt_key", "snapshot_hash", "cached", "abstained"}
    assert PromptCache(tmp_path).get(key)["parsed"] == json.loads(BULLISH)
    assert second.metadata["cached"] is True


def test_provider_metadata_cannot_override_signal_fields(tmp_path):
    metadata = {"abstained": True, "confidence": 0, "cached": True, "model": "wrong", "signal": "bearish"}
    payload = {**json.loads(BULLISH), "provider_metadata": metadata}
    agent = BuffettAgent(llm=FakeLLM(json.dumps(payload)), cache=PromptCache(tmp_path))
    signal = agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    assert signal.value == 0.8
    assert signal.metadata["abstained"] is signal.metadata["cached"] is False
    assert signal.metadata["confidence"] == 80
    assert signal.metadata["signal"] == "bullish"
    assert signal.metadata["model"] == "fake-model"
    assert signal.metadata["provider_metadata"] == metadata


def test_invalid_provider_metadata_is_a_parse_failure(tmp_path):
    payload = {**json.loads(BULLISH), "provider_metadata": []}
    agent = BuffettAgent(llm=FakeLLM(json.dumps(payload)), cache=PromptCache(tmp_path))
    signal = agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    assert signal.metadata["abstained"] is True
    assert "provider_metadata" in signal.metadata["abstain_reason"]


def test_ordinary_call_error_without_diagnostics_preserves_failure_shape(tmp_path):
    agent = BuffettAgent(llm=FakeLLM(error=LLMCallError("failed")), cache=PromptCache(tmp_path))
    signal = agent.predict("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    assert signal.metadata == {"abstained": True, "abstain_reason": "LLM call failed: failed", "cached": False}
    assert not list(tmp_path.glob("*.json"))
