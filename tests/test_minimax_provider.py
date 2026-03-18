import os
import pytest
from unittest.mock import patch, MagicMock

from src.llm.models import (
    ModelProvider,
    LLMModel,
    get_model,
    get_model_info,
    find_model_by_name,
    AVAILABLE_MODELS,
)


class TestMiniMaxProviderEnum:
    """Test that MiniMax is properly registered as a provider."""

    def test_minimax_enum_exists(self):
        assert hasattr(ModelProvider, "MINIMAX")
        assert ModelProvider.MINIMAX.value == "MiniMax"

    def test_minimax_enum_is_string(self):
        assert isinstance(ModelProvider.MINIMAX, str)
        assert ModelProvider.MINIMAX == "MiniMax"


class TestMiniMaxModelConfig:
    """Test MiniMax model configuration in api_models.json."""

    def test_minimax_m27_in_available_models(self):
        model = find_model_by_name("MiniMax-M2.7")
        assert model is not None
        assert model.display_name == "MiniMax M2.7"
        assert model.model_name == "MiniMax-M2.7"
        assert model.provider == ModelProvider.MINIMAX

    def test_minimax_m27_highspeed_in_available_models(self):
        model = find_model_by_name("MiniMax-M2.7-highspeed")
        assert model is not None
        assert model.display_name == "MiniMax M2.7 High Speed"
        assert model.model_name == "MiniMax-M2.7-highspeed"
        assert model.provider == ModelProvider.MINIMAX

    def test_minimax_m27_is_default(self):
        """M2.7 should appear before M2.5 in the model list."""
        minimax_models = [m for m in AVAILABLE_MODELS if m.provider == ModelProvider.MINIMAX]
        assert len(minimax_models) >= 2
        assert minimax_models[0].model_name == "MiniMax-M2.7"
        assert minimax_models[1].model_name == "MiniMax-M2.7-highspeed"

    def test_minimax_m25_in_available_models(self):
        model = find_model_by_name("MiniMax-M2.5")
        assert model is not None
        assert model.display_name == "MiniMax M2.5"
        assert model.model_name == "MiniMax-M2.5"
        assert model.provider == ModelProvider.MINIMAX

    def test_minimax_m25_highspeed_in_available_models(self):
        model = find_model_by_name("MiniMax-M2.5-highspeed")
        assert model is not None
        assert model.display_name == "MiniMax M2.5 High Speed"
        assert model.model_name == "MiniMax-M2.5-highspeed"
        assert model.provider == ModelProvider.MINIMAX

    def test_get_model_info_minimax(self):
        model_info = get_model_info("MiniMax-M2.7", "MiniMax")
        assert model_info is not None
        assert model_info.provider == ModelProvider.MINIMAX


class TestMiniMaxModelProperties:
    """Test MiniMax model behavior properties."""

    def test_minimax_has_no_json_mode(self):
        model = LLMModel(
            display_name="MiniMax M2.5",
            model_name="MiniMax-M2.5",
            provider=ModelProvider.MINIMAX,
        )
        assert model.has_json_mode() is False

    def test_minimax_is_minimax(self):
        model = LLMModel(
            display_name="MiniMax M2.5",
            model_name="MiniMax-M2.5",
            provider=ModelProvider.MINIMAX,
        )
        assert model.is_minimax() is True

    def test_minimax_is_not_deepseek(self):
        model = LLMModel(
            display_name="MiniMax M2.5",
            model_name="MiniMax-M2.5",
            provider=ModelProvider.MINIMAX,
        )
        assert model.is_deepseek() is False

    def test_minimax_is_not_ollama(self):
        model = LLMModel(
            display_name="MiniMax M2.5",
            model_name="MiniMax-M2.5",
            provider=ModelProvider.MINIMAX,
        )
        assert model.is_ollama() is False

    def test_minimax_to_choice_tuple(self):
        model = LLMModel(
            display_name="MiniMax M2.5",
            model_name="MiniMax-M2.5",
            provider=ModelProvider.MINIMAX,
        )
        assert model.to_choice_tuple() == ("MiniMax M2.5", "MiniMax-M2.5", "MiniMax")


class TestMiniMaxGetModel:
    """Test get_model() factory for MiniMax provider."""

    @patch("src.llm.models.ChatOpenAI")
    def test_get_model_with_api_key(self, mock_chat_openai):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        result = get_model(
            "MiniMax-M2.5",
            ModelProvider.MINIMAX,
            api_keys={"MINIMAX_API_KEY": "test-key"},
        )

        mock_chat_openai.assert_called_once_with(
            model="MiniMax-M2.5",
            api_key="test-key",
            base_url="https://api.minimax.io/v1",
        )
        assert result == mock_instance

    @patch("src.llm.models.ChatOpenAI")
    @patch.dict(os.environ, {"MINIMAX_API_KEY": "env-test-key"})
    def test_get_model_with_env_api_key(self, mock_chat_openai):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        result = get_model("MiniMax-M2.5", ModelProvider.MINIMAX)

        mock_chat_openai.assert_called_once_with(
            model="MiniMax-M2.5",
            api_key="env-test-key",
            base_url="https://api.minimax.io/v1",
        )
        assert result == mock_instance

    @patch.dict(os.environ, {}, clear=True)
    def test_get_model_raises_without_api_key(self):
        # Remove MINIMAX_API_KEY from env if present
        os.environ.pop("MINIMAX_API_KEY", None)
        with pytest.raises(ValueError, match="MiniMax API key not found"):
            get_model("MiniMax-M2.5", ModelProvider.MINIMAX)

    @patch("src.llm.models.ChatOpenAI")
    @patch.dict(
        os.environ,
        {
            "MINIMAX_API_KEY": "test-key",
            "MINIMAX_BASE_URL": "https://api.minimaxi.com/v1",
        },
    )
    def test_get_model_with_custom_base_url(self, mock_chat_openai):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        result = get_model("MiniMax-M2.5", ModelProvider.MINIMAX)

        mock_chat_openai.assert_called_once_with(
            model="MiniMax-M2.5",
            api_key="test-key",
            base_url="https://api.minimaxi.com/v1",
        )
        assert result == mock_instance

    @patch("src.llm.models.ChatOpenAI")
    def test_get_model_m27(self, mock_chat_openai):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        result = get_model(
            "MiniMax-M2.7",
            ModelProvider.MINIMAX,
            api_keys={"MINIMAX_API_KEY": "test-key"},
        )

        mock_chat_openai.assert_called_once_with(
            model="MiniMax-M2.7",
            api_key="test-key",
            base_url="https://api.minimax.io/v1",
        )
        assert result == mock_instance

    @patch("src.llm.models.ChatOpenAI")
    def test_get_model_m27_highspeed(self, mock_chat_openai):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        result = get_model(
            "MiniMax-M2.7-highspeed",
            ModelProvider.MINIMAX,
            api_keys={"MINIMAX_API_KEY": "test-key"},
        )

        mock_chat_openai.assert_called_once_with(
            model="MiniMax-M2.7-highspeed",
            api_key="test-key",
            base_url="https://api.minimax.io/v1",
        )
        assert result == mock_instance

    @patch("src.llm.models.ChatOpenAI")
    def test_get_model_highspeed(self, mock_chat_openai):
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        result = get_model(
            "MiniMax-M2.5-highspeed",
            ModelProvider.MINIMAX,
            api_keys={"MINIMAX_API_KEY": "test-key"},
        )

        mock_chat_openai.assert_called_once_with(
            model="MiniMax-M2.5-highspeed",
            api_key="test-key",
            base_url="https://api.minimax.io/v1",
        )
        assert result == mock_instance
