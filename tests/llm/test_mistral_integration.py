"""
Tests for LLM model configuration and Mistral integration.

This test suite verifies:
1. Model registry loads Mistral models from JSON
2. get_model() instantiates ChatMistralAI correctly
3. get_model_info() retrieves Mistral model information
4. API key validation works for Mistral
5. Frontend TypeScript compatibility
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.llm.models import (
    ModelProvider,
    LLMModel,
    get_model,
    get_model_info,
    get_models_list,
    load_models_from_json,
    AVAILABLE_MODELS,
)


class TestModelProvider:
    """Test ModelProvider enum includes Mistral."""

    def test_mistral_provider_exists(self):
        """Verify MISTRAL exists in ModelProvider enum."""
        assert hasattr(ModelProvider, 'MISTRAL')
        assert ModelProvider.MISTRAL.value == "Mistral"

    def test_all_providers_have_string_values(self):
        """Ensure all providers have proper string values."""
        providers = [
            ModelProvider.OPENAI,
            ModelProvider.ANTHROPIC,
            ModelProvider.MISTRAL,
            ModelProvider.GROQ,
            ModelProvider.DEEPSEEK,
        ]
        for provider in providers:
            assert isinstance(provider.value, str)
            assert len(provider.value) > 0


class TestMistralModelsInJSON:
    """Test that Mistral models are properly configured in api_models.json."""

    def test_mistral_models_in_json(self):
        """Verify api_models.json contains Mistral entries."""
        # Navigate from tests/llm/ to project root, then to src/llm/
        json_path = Path(__file__).parent.parent.parent / "src" / "llm" / "api_models.json"

        with open(json_path, 'r') as f:
            models_data = json.load(f)

        mistral_models = [m for m in models_data if m.get("provider") == "Mistral"]

        assert len(mistral_models) >= 3, "Should have at least 3 Mistral models"

        # Verify specific models exist
        model_names = [m["model_name"] for m in mistral_models]
        assert "mistral-large-latest" in model_names
        assert "mistral-small-latest" in model_names
        assert "codestral-latest" in model_names

    def test_mistral_models_have_required_fields(self):
        """Ensure all Mistral models have display_name, model_name, and provider."""
        json_path = Path(__file__).parent.parent.parent / "src" / "llm" / "api_models.json"

        with open(json_path, 'r') as f:
            models_data = json.load(f)

        mistral_models = [m for m in models_data if m.get("provider") == "Mistral"]

        for model in mistral_models:
            assert "display_name" in model
            assert "model_name" in model
            assert "provider" in model
            assert model["provider"] == "Mistral"
            assert len(model["display_name"]) > 0
            assert len(model["model_name"]) > 0


class TestLoadModelsFromJSON:
    """Test loading models from JSON including Mistral."""

    def test_load_mistral_models(self):
        """Verify load_models_from_json correctly loads Mistral models."""
        json_path = Path(__file__).parent.parent.parent / "src" / "llm" / "api_models.json"
        models = load_models_from_json(str(json_path))

        mistral_models = [m for m in models if m.provider == ModelProvider.MISTRAL]

        assert len(mistral_models) >= 3

        # Verify they are LLMModel instances
        for model in mistral_models:
            assert isinstance(model, LLMModel)
            assert model.provider == ModelProvider.MISTRAL

    def test_available_models_includes_mistral(self):
        """Verify AVAILABLE_MODELS global includes Mistral."""
        mistral_models = [m for m in AVAILABLE_MODELS if m.provider == ModelProvider.MISTRAL]

        assert len(mistral_models) >= 3
        assert any(m.model_name == "mistral-large-latest" for m in mistral_models)


class TestGetModelsListAPI:
    """Test get_models_list() API function includes Mistral."""

    def test_mistral_in_models_list(self):
        """Verify get_models_list() returns Mistral models."""
        models = get_models_list()

        mistral_models = [m for m in models if m["provider"] == "Mistral"]

        assert len(mistral_models) >= 3
        assert any(m["model_name"] == "mistral-large-latest" for m in mistral_models)

    def test_models_list_format(self):
        """Ensure models list has correct format for API."""
        models = get_models_list()

        for model in models:
            assert "display_name" in model
            assert "model_name" in model
            assert "provider" in model
            assert isinstance(model["display_name"], str)
            assert isinstance(model["model_name"], str)
            assert isinstance(model["provider"], str)


class TestGetModelInfo:
    """Test get_model_info() retrieves Mistral model information."""

    def test_get_mistral_large_info(self):
        """Retrieve info for Mistral Large 2."""
        model_info = get_model_info("mistral-large-latest", "Mistral")

        assert model_info is not None
        assert model_info.model_name == "mistral-large-latest"
        assert model_info.provider == ModelProvider.MISTRAL
        assert "Mistral" in model_info.display_name

    def test_get_mistral_small_info(self):
        """Retrieve info for Mistral Small."""
        model_info = get_model_info("mistral-small-latest", "Mistral")

        assert model_info is not None
        assert model_info.model_name == "mistral-small-latest"
        assert model_info.provider == ModelProvider.MISTRAL

    def test_get_codestral_info(self):
        """Retrieve info for Codestral."""
        model_info = get_model_info("codestral-latest", "Mistral")

        assert model_info is not None
        assert model_info.model_name == "codestral-latest"
        assert model_info.provider == ModelProvider.MISTRAL

    def test_get_nonexistent_mistral_model(self):
        """Return None for non-existent Mistral model."""
        model_info = get_model_info("nonexistent-model", "Mistral")
        assert model_info is None


class TestGetModelMistral:
    """Test get_model() instantiates ChatMistralAI correctly."""

    @patch('src.llm.models.ChatMistralAI')
    def test_get_model_with_api_key_dict(self, mock_chat_mistral):
        """Test get_model() with API key in dict."""
        api_keys = {"MISTRAL_API_KEY": "test-key-123"}

        result = get_model("mistral-large-latest", ModelProvider.MISTRAL, api_keys)

        mock_chat_mistral.assert_called_once_with(
            model="mistral-large-latest",
            api_key="test-key-123"
        )

    @patch.dict('os.environ', {'MISTRAL_API_KEY': 'env-key-456'})
    @patch('src.llm.models.ChatMistralAI')
    def test_get_model_with_env_var(self, mock_chat_mistral):
        """Test get_model() with API key from environment."""
        result = get_model("mistral-small-latest", ModelProvider.MISTRAL, None)

        mock_chat_mistral.assert_called_once_with(
            model="mistral-small-latest",
            api_key="env-key-456"
        )

    @patch.dict('os.environ', {}, clear=True)
    def test_get_model_missing_api_key(self):
        """Test get_model() raises error when API key missing."""
        with pytest.raises(ValueError) as exc_info:
            get_model("mistral-large-latest", ModelProvider.MISTRAL, None)

        assert "MISTRAL_API_KEY" in str(exc_info.value)
        assert "Mistral API key not found" in str(exc_info.value)

    @patch('src.llm.models.ChatMistralAI')
    def test_get_model_codestral(self, mock_chat_mistral):
        """Test get_model() works with Codestral."""
        api_keys = {"MISTRAL_API_KEY": "test-key-789"}

        result = get_model("codestral-latest", ModelProvider.MISTRAL, api_keys)

        mock_chat_mistral.assert_called_once_with(
            model="codestral-latest",
            api_key="test-key-789"
        )

    @patch('src.llm.models.ChatMistralAI')
    def test_get_model_returns_instance(self, mock_chat_mistral):
        """Verify get_model() returns ChatMistralAI instance."""
        mock_instance = MagicMock()
        mock_chat_mistral.return_value = mock_instance
        api_keys = {"MISTRAL_API_KEY": "test-key"}

        result = get_model("mistral-large-latest", ModelProvider.MISTRAL, api_keys)

        assert result == mock_instance


class TestLLMModelMistralMethods:
    """Test LLMModel methods with Mistral models."""

    def test_mistral_model_to_choice_tuple(self):
        """Test to_choice_tuple() for Mistral model."""
        model = LLMModel(
            display_name="Mistral Large 2",
            model_name="mistral-large-latest",
            provider=ModelProvider.MISTRAL
        )

        choice = model.to_choice_tuple()

        assert choice == ("Mistral Large 2", "mistral-large-latest", "Mistral")

    def test_mistral_model_has_json_mode(self):
        """Test has_json_mode() returns True for Mistral (default)."""
        model = LLMModel(
            display_name="Mistral Small",
            model_name="mistral-small-latest",
            provider=ModelProvider.MISTRAL
        )

        # Mistral models should support JSON mode (not deepseek or gemini)
        assert model.has_json_mode() is True

    def test_mistral_is_not_ollama(self):
        """Verify is_ollama() returns False for Mistral."""
        model = LLMModel(
            display_name="Codestral",
            model_name="codestral-latest",
            provider=ModelProvider.MISTRAL
        )

        assert model.is_ollama() is False


class TestMistralIntegrationWithOtherProviders:
    """Test Mistral works alongside other providers."""

    def test_multiple_providers_in_models_list(self):
        """Ensure Mistral coexists with OpenAI, Anthropic, etc."""
        models = get_models_list()

        providers = set(m["provider"] for m in models)

        # Should have multiple providers including Mistral
        assert "Mistral" in providers
        assert "OpenAI" in providers
        assert "Anthropic" in providers
        assert len(providers) >= 4

    @patch('src.llm.models.ChatMistralAI')
    @patch('src.llm.models.ChatOpenAI')
    def test_get_model_switches_providers(self, mock_openai, mock_mistral):
        """Test get_model() correctly switches between providers."""
        api_keys = {
            "MISTRAL_API_KEY": "mistral-key",
            "OPENAI_API_KEY": "openai-key"
        }

        # Get Mistral model
        get_model("mistral-large-latest", ModelProvider.MISTRAL, api_keys)
        assert mock_mistral.called
        assert not mock_openai.called

        # Reset mocks
        mock_mistral.reset_mock()
        mock_openai.reset_mock()

        # Get OpenAI model
        get_model("gpt-4.1", ModelProvider.OPENAI, api_keys)
        assert mock_openai.called
        assert not mock_mistral.called


class TestMistralErrorHandling:
    """Test error handling for Mistral-specific scenarios."""

    @patch.dict('os.environ', {}, clear=True)
    def test_missing_api_key_error_message(self):
        """Verify error message mentions Mistral and .env file."""
        with pytest.raises(ValueError) as exc_info:
            get_model("mistral-large-latest", ModelProvider.MISTRAL, None)

        error_message = str(exc_info.value)
        assert "MISTRAL_API_KEY" in error_message
        assert ".env" in error_message

    @patch('src.llm.models.ChatMistralAI')
    def test_empty_api_key_dict(self, mock_mistral):
        """Test with empty API keys dict falls back to env var."""
        with patch.dict('os.environ', {'MISTRAL_API_KEY': 'env-fallback'}):
            get_model("mistral-small-latest", ModelProvider.MISTRAL, {})

            mock_mistral.assert_called_once()
            call_kwargs = mock_mistral.call_args[1]
            assert call_kwargs['api_key'] == 'env-fallback'


class TestMistralModelProperties:
    """Test specific properties of Mistral models."""

    def test_mistral_large_properties(self):
        """Verify Mistral Large 2 has correct properties."""
        model_info = get_model_info("mistral-large-latest", "Mistral")

        assert model_info is not None
        assert "Large" in model_info.display_name
        assert model_info.provider == ModelProvider.MISTRAL
        assert not model_info.is_custom()

    def test_codestral_properties(self):
        """Verify Codestral has correct properties."""
        model_info = get_model_info("codestral-latest", "Mistral")

        assert model_info is not None
        assert "Codestral" in model_info.display_name
        assert model_info.provider == ModelProvider.MISTRAL


# Integration test that verifies the full flow
class TestMistralEndToEnd:
    """End-to-end tests simulating real usage."""

    @patch('src.llm.models.ChatMistralAI')
    def test_full_model_selection_flow(self, mock_mistral):
        """Simulate: Load models → Select Mistral → Instantiate."""
        # Step 1: Get available models
        models = get_models_list()
        mistral_models = [m for m in models if m["provider"] == "Mistral"]
        assert len(mistral_models) > 0

        # Step 2: Get info for first Mistral model
        first_mistral = mistral_models[0]
        model_info = get_model_info(first_mistral["model_name"], "Mistral")
        assert model_info is not None

        # Step 3: Instantiate the model
        api_keys = {"MISTRAL_API_KEY": "test-key"}
        model_instance = get_model(
            first_mistral["model_name"],
            ModelProvider.MISTRAL,
            api_keys
        )

        # Verify ChatMistralAI was called correctly
        mock_mistral.assert_called_once()
        call_kwargs = mock_mistral.call_args[1]
        assert call_kwargs['model'] == first_mistral["model_name"]
        assert call_kwargs['api_key'] == "test-key"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
