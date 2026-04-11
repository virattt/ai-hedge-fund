"""
Tests for the language models API endpoint with Mistral support.

Tests the FastAPI endpoint that serves available models to the frontend.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.backend.main import app


client = TestClient(app)


class TestLanguageModelsEndpoint:
    """Test /language-models/ endpoint returns Mistral models."""

    def test_get_language_models_includes_mistral(self):
        """Verify GET /language-models/ returns Mistral models."""
        response = client.get("/language-models/")

        assert response.status_code == 200
        data = response.json()

        assert "models" in data
        models = data["models"]

        # Filter for Mistral models
        mistral_models = [m for m in models if m.get("provider") == "Mistral"]

        assert len(mistral_models) >= 3, "Should have at least 3 Mistral models"

        # Verify specific models
        model_names = [m["model_name"] for m in mistral_models]
        assert "mistral-large-latest" in model_names
        assert "mistral-small-latest" in model_names
        assert "codestral-latest" in model_names

    def test_language_models_response_structure(self):
        """Ensure response has correct structure."""
        response = client.get("/language-models/")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, dict)
        assert "models" in data
        assert isinstance(data["models"], list)

        # Check each model has required fields
        for model in data["models"]:
            assert "display_name" in model
            assert "model_name" in model
            assert "provider" in model

    def test_mistral_models_format(self):
        """Verify Mistral models have correct format."""
        response = client.get("/language-models/")
        data = response.json()

        mistral_models = [m for m in data["models"] if m.get("provider") == "Mistral"]

        for model in mistral_models:
            assert isinstance(model["display_name"], str)
            assert isinstance(model["model_name"], str)
            assert model["provider"] == "Mistral"
            assert len(model["display_name"]) > 0
            assert len(model["model_name"]) > 0


class TestLanguageModelProvidersEndpoint:
    """Test /language-models/providers endpoint includes Mistral."""

    def test_get_providers_includes_mistral(self):
        """Verify GET /language-models/providers includes Mistral."""
        response = client.get("/language-models/providers")

        assert response.status_code == 200
        data = response.json()

        assert "providers" in data
        providers = data["providers"]

        # Find Mistral provider
        mistral_provider = next((p for p in providers if p["name"] == "Mistral"), None)

        assert mistral_provider is not None, "Mistral should be in providers list"
        assert "models" in mistral_provider
        assert len(mistral_provider["models"]) >= 3

    def test_mistral_provider_models_structure(self):
        """Verify Mistral provider has correctly structured models."""
        response = client.get("/language-models/providers")
        data = response.json()

        mistral_provider = next(
            (p for p in data["providers"] if p["name"] == "Mistral"),
            None
        )

        assert mistral_provider is not None

        for model in mistral_provider["models"]:
            assert "display_name" in model
            assert "model_name" in model
            assert isinstance(model["display_name"], str)
            assert isinstance(model["model_name"], str)


class TestLanguageModelsWithOllama:
    """Test that Ollama models and Mistral both appear in response."""

    def test_mistral_models_present(self):
        """Ensure Mistral models are always present regardless of Ollama status."""
        response = client.get("/language-models/")

        assert response.status_code == 200
        data = response.json()

        assert "models" in data
        providers = set(m["provider"] for m in data["models"])

        # Mistral should always be present (from api_models.json)
        assert "Mistral" in providers

        # Mistral models should definitely be there
        mistral_models = [m for m in data["models"] if m["provider"] == "Mistral"]
        assert len(mistral_models) >= 3


class TestAPIErrorHandling:
    """Test API error handling for language models endpoint."""

    @patch('app.backend.routes.language_models.get_models_list')
    def test_handles_exception_gracefully(self, mock_get_models):
        """Verify endpoint handles exceptions gracefully."""
        mock_get_models.side_effect = Exception("Test error")

        response = client.get("/language-models/")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


class TestMistralModelsConsistency:
    """Test consistency between different endpoints."""

    def test_models_consistent_across_endpoints(self):
        """Verify /language-models/ and /providers return same Mistral models."""
        # Get models from main endpoint
        response1 = client.get("/language-models/")
        models_data = response1.json()
        mistral_from_models = [m for m in models_data["models"] if m["provider"] == "Mistral"]

        # Get models from providers endpoint
        response2 = client.get("/language-models/providers")
        providers_data = response2.json()
        mistral_provider = next(
            (p for p in providers_data["providers"] if p["name"] == "Mistral"),
            None
        )

        assert mistral_provider is not None
        mistral_from_providers = mistral_provider["models"]

        # Should have same number of models
        assert len(mistral_from_models) == len(mistral_from_providers)

        # Model names should match
        names_from_models = set(m["model_name"] for m in mistral_from_models)
        names_from_providers = set(m["model_name"] for m in mistral_from_providers)
        assert names_from_models == names_from_providers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
