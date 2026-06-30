from src.cli.input import select_analysts, select_model


def test_select_analysts_accepts_cli_flags():
    analysts = select_analysts({"analysts": "ben_graham,warren_buffett"})

    assert analysts == ["ben_graham", "warren_buffett"]


def test_select_analysts_all_accepts_cli_flag():
    analysts = select_analysts({"analysts_all": True})

    assert "ben_graham" in analysts
    assert "warren_buffett" in analysts
    assert len(analysts) > 2


def test_select_model_accepts_openrouter_model_flag(monkeypatch):
    monkeypatch.delenv("AI_HEDGE_FUND_LLM_MODEL", raising=False)
    monkeypatch.delenv("AI_HEDGE_FUND_LLM_PROVIDER", raising=False)

    model_name, model_provider = select_model(
        use_ollama=False,
        model_flag="z-ai/glm-5.2",
    )

    assert model_name == "z-ai/glm-5.2"
    assert model_provider == "OpenRouter"


def test_select_model_uses_env_defaults(monkeypatch):
    monkeypatch.setenv("AI_HEDGE_FUND_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("AI_HEDGE_FUND_LLM_MODEL", "z-ai/glm-5.2")

    model_name, model_provider = select_model(use_ollama=False)

    assert model_name == "z-ai/glm-5.2"
    assert model_provider == "OpenRouter"
