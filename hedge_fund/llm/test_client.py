"""Every provider must construct, and every response shape must flatten.

The constructor tests are the point: a wrong kwarg name for one provider is a
TypeError that would otherwise surface only mid-run, after minutes of warming.
Nothing here touches the network — building a langchain chat model does not
call the API.
"""

from __future__ import annotations

import pytest

from hedge_fund.llm import ChatLLM, SUPPORTED_PROVIDERS, load_api_models, make_llm, provider_for
from hedge_fund.llm.client import _flatten
from hedge_fund.llm.registry import PROVIDER_ENV_VARS

# One model id per provider, taken from the registry so this test fails loudly
# if a provider is dropped from api_models.json.
_BY_PROVIDER = {prov: mid for _, mid, prov in load_api_models()}


@pytest.fixture
def keyed(monkeypatch):
    """Every provider key present, so make_llm gets past its key check."""
    for env_var in PROVIDER_ENV_VARS.values():
        monkeypatch.setenv(env_var, "test-key-not-real")
    monkeypatch.delenv("HEDGE_FUND_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)


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


def test_kimi_accepts_moonshot_key(monkeypatch):
    """v1 reads MOONSHOT_API_KEY first; the same .env must work here."""
    monkeypatch.delenv("HEDGE_FUND_LLM_MODEL", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.setenv("MOONSHOT_API_KEY", "test-key-not-real")
    assert make_llm(_BY_PROVIDER["Kimi"]).model == _BY_PROVIDER["Kimi"]


def test_provider_for_reads_the_registry():
    assert provider_for("claude-opus-5") == "Anthropic"
    assert provider_for("gpt-5.5") == "OpenAI"
    assert provider_for("not-a-model") is None


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
