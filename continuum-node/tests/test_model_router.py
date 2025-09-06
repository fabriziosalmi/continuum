"""Test module for ModelRouter service."""
import pytest
import yaml
import unittest.mock as mock
from unittest.mock import patch, mock_open, MagicMock

from app.services.model_router import ModelRouter
from app.providers.base_provider import BaseProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider


class MockProvider(BaseProvider):
    """Mock provider for testing."""
    
    async def stream_completion(self, messages, settings):
        """Mock stream completion."""
        yield "mock response"


class TestModelRouter:
    """Test class for ModelRouter functionality."""

    def setup_method(self):
        """Setup method called before each test."""
        self.model_router = ModelRouter()

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    @patch("app.services.model_router.OllamaProvider")
    @patch("app.services.model_router.OpenAIProvider")
    def test_load_models_success(self, mock_openai_provider, mock_ollama_provider, mock_yaml_load, mock_file):
        """Test successful loading of models from YAML file."""
        # Setup mock providers
        mock_ollama_instance = MockProvider()
        mock_openai_instance = MockProvider()
        mock_ollama_provider.return_value = mock_ollama_instance
        mock_openai_provider.return_value = mock_openai_instance
        mock_openai_provider.return_value.api_key = "test-key"

        # Mock YAML content
        mock_yaml_content = {
            "models": [
                {
                    "id": "llama3:latest",
                    "provider": "ollama"
                },
                {
                    "id": "gpt-4o",
                    "provider": "openai"
                }
            ]
        }
        mock_yaml_load.return_value = mock_yaml_content

        # Load models
        self.model_router.load_models("fake_models.yml")

        # Verify models were loaded correctly
        assert len(self.model_router.model_providers) == 2
        assert "llama3:latest" in self.model_router.model_providers
        assert "gpt-4o" in self.model_router.model_providers
        
        assert len(self.model_router.model_configs) == 2
        assert self.model_router.model_configs["llama3:latest"]["provider"] == "ollama"
        assert self.model_router.model_configs["gpt-4o"]["provider"] == "openai"

        # Verify provider instances were created
        mock_ollama_provider.assert_called_once()
        mock_openai_provider.assert_called_once()

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_load_models_file_not_found(self, mock_file):
        """Test handling of missing YAML file."""
        with pytest.raises(FileNotFoundError, match="File di configurazione modelli non trovato"):
            self.model_router.load_models("nonexistent.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load", side_effect=yaml.YAMLError("Invalid YAML"))
    def test_load_models_invalid_yaml(self, mock_yaml_load, mock_file):
        """Test handling of invalid YAML content."""
        with pytest.raises(ValueError, match="Errore nel parsing del file YAML"):
            self.model_router.load_models("invalid.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_models_missing_models_section(self, mock_yaml_load, mock_file):
        """Test handling of YAML file without 'models' section."""
        mock_yaml_load.return_value = {"invalid": "structure"}
        
        with pytest.raises(ValueError, match="File di configurazione modelli non valido"):
            self.model_router.load_models("invalid_structure.yml")

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_models_missing_required_field(self, mock_yaml_load, mock_file):
        """Test handling of models with missing required fields."""
        mock_yaml_content = {
            "models": [
                {
                    "provider": "ollama"
                    # Missing 'id' field
                }
            ]
        }
        mock_yaml_load.return_value = mock_yaml_content

        with pytest.raises(ValueError, match="Campo richiesto mancante"):
            self.model_router.load_models("missing_field.yml")

    @patch("app.services.model_router.OllamaProvider")
    def test_create_provider_ollama(self, mock_ollama_provider):
        """Test creation of Ollama provider."""
        mock_instance = MockProvider()
        mock_ollama_provider.return_value = mock_instance

        provider = self.model_router._create_provider("ollama")
        assert provider is mock_instance
        mock_ollama_provider.assert_called_once()

    @patch("app.services.model_router.OllamaProvider")
    def test_create_provider_ollama_case_insensitive(self, mock_ollama_provider):
        """Test creation of Ollama provider with different case."""
        mock_instance = MockProvider()
        mock_ollama_provider.return_value = mock_instance

        provider = self.model_router._create_provider("OLLAMA")
        assert provider is mock_instance

        provider = self.model_router._create_provider("Ollama")
        assert provider is mock_instance

    @patch("app.services.model_router.OpenAIProvider")
    def test_create_provider_openai_with_api_key(self, mock_openai_provider):
        """Test creation of OpenAI provider with valid API key."""
        mock_instance = MockProvider()
        mock_instance.api_key = "test-api-key"
        mock_openai_provider.return_value = mock_instance

        provider = self.model_router._create_provider("openai")
        assert provider is mock_instance
        mock_openai_provider.assert_called_once()

    @patch("app.services.model_router.OpenAIProvider")
    def test_create_provider_openai_without_api_key(self, mock_openai_provider):
        """Test creation of OpenAI provider without API key."""
        mock_instance = MockProvider()
        mock_instance.api_key = None  # No API key
        mock_openai_provider.return_value = mock_instance

        provider = self.model_router._create_provider("openai")
        assert provider is None  # Should return None when no API key

    @patch("app.services.model_router.OpenAIProvider")
    def test_create_provider_openai_case_insensitive(self, mock_openai_provider):
        """Test creation of OpenAI provider with different case."""
        mock_instance = MockProvider()
        mock_instance.api_key = "test-key"
        mock_openai_provider.return_value = mock_instance

        provider = self.model_router._create_provider("OPENAI")
        assert provider is mock_instance

        provider = self.model_router._create_provider("OpenAI")
        assert provider is mock_instance

    def test_create_provider_unsupported(self):
        """Test creation of unsupported provider type."""
        provider = self.model_router._create_provider("unsupported_provider")
        assert provider is None

    @patch("app.services.model_router.OllamaProvider", side_effect=Exception("Provider creation failed"))
    def test_create_provider_creation_error(self, mock_ollama_provider):
        """Test handling of provider creation errors."""
        provider = self.model_router._create_provider("ollama")
        assert provider is None

    def test_get_provider_for_model_existing(self):
        """Test getting provider for existing model."""
        # Setup a model with provider
        mock_provider = MockProvider()
        self.model_router.model_providers["test-model"] = mock_provider

        provider = self.model_router.get_provider_for_model("test-model")
        assert provider is mock_provider

    def test_get_provider_for_model_nonexistent(self):
        """Test getting provider for non-existent model."""
        provider = self.model_router.get_provider_for_model("nonexistent-model")
        assert provider is None

    def test_get_available_models_empty(self):
        """Test getting available models when no models are loaded."""
        models = self.model_router.get_available_models()
        assert models == []

    def test_get_available_models_with_models(self):
        """Test getting available models when models are loaded."""
        # Setup some models
        mock_provider1 = MockProvider()
        mock_provider2 = MockProvider()
        self.model_router.model_providers["model1"] = mock_provider1
        self.model_router.model_providers["model2"] = mock_provider2

        models = self.model_router.get_available_models()
        assert set(models) == {"model1", "model2"}

    def test_get_model_config_existing(self):
        """Test getting config for existing model."""
        # Setup model config
        config = {"id": "test-model", "provider": "ollama"}
        self.model_router.model_configs["test-model"] = config

        retrieved_config = self.model_router.get_model_config("test-model")
        assert retrieved_config == config

    def test_get_model_config_nonexistent(self):
        """Test getting config for non-existent model."""
        config = self.model_router.get_model_config("nonexistent-model")
        assert config is None

    def test_is_model_available_existing(self):
        """Test checking availability of existing model."""
        # Setup a model
        mock_provider = MockProvider()
        self.model_router.model_providers["available-model"] = mock_provider

        assert self.model_router.is_model_available("available-model") is True

    def test_is_model_available_nonexistent(self):
        """Test checking availability of non-existent model."""
        assert self.model_router.is_model_available("nonexistent-model") is False

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    @patch("app.services.model_router.OllamaProvider")
    def test_load_models_with_unsupported_provider(self, mock_ollama_provider, mock_yaml_load, mock_file):
        """Test loading models with unsupported provider type."""
        mock_ollama_instance = MockProvider()
        mock_ollama_provider.return_value = mock_ollama_instance

        # Mock YAML content with unsupported provider
        mock_yaml_content = {
            "models": [
                {
                    "id": "good-model",
                    "provider": "ollama"
                },
                {
                    "id": "bad-model", 
                    "provider": "unsupported_provider"
                }
            ]
        }
        mock_yaml_load.return_value = mock_yaml_content

        # Load models
        self.model_router.load_models("test.yml")

        # Verify only supported model was loaded
        assert "good-model" in self.model_router.model_providers
        assert "bad-model" not in self.model_router.model_providers
        
        # But config should still be stored for both
        assert "good-model" in self.model_router.model_configs
        assert "bad-model" in self.model_router.model_configs

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    @patch("app.services.model_router.OllamaProvider")
    @patch("app.services.model_router.OpenAIProvider")
    def test_load_models_mixed_success_and_failure(self, mock_openai_provider, mock_ollama_provider, mock_yaml_load, mock_file):
        """Test loading models with mix of successful and failed provider creations."""
        # Setup providers - Ollama succeeds, OpenAI fails due to no API key
        mock_ollama_instance = MockProvider()
        mock_ollama_provider.return_value = mock_ollama_instance

        mock_openai_instance = MockProvider()
        mock_openai_instance.api_key = None  # No API key
        mock_openai_provider.return_value = mock_openai_instance

        mock_yaml_content = {
            "models": [
                {
                    "id": "llama3:latest",
                    "provider": "ollama"
                },
                {
                    "id": "gpt-4o",
                    "provider": "openai"
                }
            ]
        }
        mock_yaml_load.return_value = mock_yaml_content

        # Load models
        self.model_router.load_models("test.yml")

        # Verify only Ollama model was loaded to providers
        assert "llama3:latest" in self.model_router.model_providers
        assert "gpt-4o" not in self.model_router.model_providers
        
        # But both configs should be stored
        assert len(self.model_router.model_configs) == 2

    @patch("builtins.open", new_callable=mock_open)
    @patch("yaml.safe_load")
    def test_load_models_complex_config(self, mock_yaml_load, mock_file):
        """Test loading models with complex configuration."""
        mock_yaml_content = {
            "models": [
                {
                    "id": "complex-model",
                    "provider": "ollama",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "custom_setting": "custom_value"
                }
            ]
        }
        mock_yaml_load.return_value = mock_yaml_content

        with patch("app.services.model_router.OllamaProvider") as mock_provider:
            mock_provider.return_value = MockProvider()
            
            # Load models
            self.model_router.load_models("test.yml")

            # Verify complex config was stored
            config = self.model_router.get_model_config("complex-model")
            assert config["temperature"] == 0.7
            assert config["max_tokens"] == 1000
            assert config["custom_setting"] == "custom_value"