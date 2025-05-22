import os
import json
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from enum import Enum
from pydantic import BaseModel
from typing import Tuple, List
from pathlib import Path


class ModelProvider(str, Enum):
    """Enum for supported LLM providers"""

    ANTHROPIC = "Anthropic"
    DEEPSEEK = "DeepSeek"
    GEMINI = "Gemini"
    GROQ = "Groq"
    OPENAI = "OpenAI"
    OLLAMA = "Ollama"


class LLMModel(BaseModel):
    """Represents an LLM model configuration"""

    display_name: str
    model_name: str
    provider: ModelProvider

    def to_choice_tuple(self) -> Tuple[str, str, str]:
        """Convert to format needed for questionary choices"""
        return (self.display_name, self.model_name, self.provider.value)

    def is_custom(self) -> bool:
        """Check if the model is a Gemini model"""
        return self.model_name == "-"

    def has_json_mode(self) -> bool:
        """Check if the model supports JSON mode"""
        if self.is_deepseek() or self.is_gemini():
            return False
        # Only certain Ollama models support JSON mode
        if self.is_ollama():
            return "llama3" in self.model_name or "neural-chat" in self.model_name
        return True

    def is_deepseek(self) -> bool:
        """Check if the model is a DeepSeek model"""
        return self.model_name.startswith("deepseek")

    def is_gemini(self) -> bool:
        """Check if the model is a Gemini model"""
        return self.model_name.startswith("gemini")

    def is_ollama(self) -> bool:
        """Check if the model is an Ollama model"""
        return self.provider == ModelProvider.OLLAMA

    def is_openai(self) -> bool:
        """Check if the model is an OpenAI model"""
        return self.provider == ModelProvider.OPENAI

# Load models from JSON file
def load_models_from_json(json_path: str, is_ollama_file: bool = False) -> List[LLMModel]:
    """Load models from a JSON file.

    Args:
        json_path: Path to the JSON file.
        is_ollama_file: Boolean indicating if the file is the ollama_models.json.
                        If True, expects a flat list of models.
                        If False, expects a dictionary grouping models by provider.
    """
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Model file not found at {json_path}")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_path}")
        return []

    models = []
    if is_ollama_file: # Ollama file has a flat list structure
        if isinstance(data, list):
            for model_data in data:
                try:
                    # Ollama models always have "Ollama" as provider
                    provider_enum = ModelProvider.OLLAMA
                    models.append(
                        LLMModel(
                            display_name=model_data["display_name"],
                            model_name=model_data["model_name"],
                            provider=provider_enum
                        )
                    )
                except KeyError as e:
                    print(f"Warning: Missing key {e} in model data in {json_path}: {model_data}")
                except ValueError as e: # Should not happen for Ollama if provider is hardcoded
                    print(f"Warning: Invalid provider value in {json_path}: {e}")
        else:
            print(f"Warning: Expected a list of models in {json_path}, but got {type(data)}")
    else: # api_models.json has models grouped by provider
        if isinstance(data, dict):
            for provider_name, model_list_data in data.items():
                try:
                    provider_enum = ModelProvider(provider_name)
                    if isinstance(model_list_data, list):
                        for model_data in model_list_data:
                            try:
                                models.append(
                                    LLMModel(
                                        display_name=model_data["display_name"],
                                        model_name=model_data["model_name"],
                                        provider=provider_enum
                                    )
                                )
                            except KeyError as e:
                                print(f"Warning: Missing key {e} in model data for provider {provider_name} in {json_path}: {model_data}")
                    else:
                        print(f"Warning: Expected a list of models for provider {provider_name} in {json_path}, but got {type(model_list_data)}")
                except ValueError:
                    print(f"Warning: Invalid provider name '{provider_name}' in {json_path}. Skipping.")
        else:
            print(f"Warning: Expected a dictionary of providers in {json_path}, but got {type(data)}")

    return models


# Get the path to the JSON files
current_dir = Path(__file__).parent
models_json_path = current_dir / "api_models.json"
ollama_models_json_path = current_dir / "ollama_models.json"

# Load available models from JSON
# For api_models.json, is_ollama_file is False (default)
AVAILABLE_MODELS = load_models_from_json(str(models_json_path))

# Load Ollama models from JSON
# For ollama_models.json, is_ollama_file is True
OLLAMA_MODELS = load_models_from_json(str(ollama_models_json_path), is_ollama_file=True)

# Create LLM_ORDER in the format expected by the UI
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]

# Create Ollama LLM_ORDER separately
OLLAMA_LLM_ORDER = [model.to_choice_tuple() for model in OLLAMA_MODELS]


def get_model_info(model_name: str, model_provider: str) -> LLMModel | None:
    """Get model information by model_name"""
    all_models = AVAILABLE_MODELS + OLLAMA_MODELS
    try:
        provider_enum = ModelProvider(model_provider)
    except ValueError:
        return None
    return next((model for model in all_models if model.model_name == model_name and model.provider == provider_enum), None)


# --- Factory functions for each provider ---

def _get_anthropic_model(model_name: str):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        # Print error to console
        print(f"API Key Error: Please make sure ANTHROPIC_API_KEY is set in your .env file.")
        raise ValueError("Anthropic API key not found. Please make sure ANTHROPIC_API_KEY is set in your .env file.")
    return ChatAnthropic(model=model_name, api_key=api_key)

def _get_deepseek_model(model_name: str):
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        # Print error to console
        print(f"API Key Error: Please make sure DEEPSEEK_API_KEY is set in your .env file.")
        raise ValueError("DeepSeek API key not found. Please make sure DEEPSEEK_API_KEY is set in your .env file.")
    return ChatDeepSeek(model=model_name, api_key=api_key)

def _get_gemini_model(model_name: str):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # Print error to console
        print(f"API Key Error: Please make sure GOOGLE_API_KEY is set in your .env file.")
        raise ValueError("Google API key not found. Please make sure GOOGLE_API_KEY is set in your .env file.")
    return ChatGoogleGenerativeAI(model=model_name, api_key=api_key)

def _get_groq_model(model_name: str):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        # Print error to console
        print(f"API Key Error: Please make sure GROQ_API_KEY is set in your .env file.")
        raise ValueError("Groq API key not found.  Please make sure GROQ_API_KEY is set in your .env file.")
    return ChatGroq(model=model_name, api_key=api_key)

def _get_openai_model(model_name: str):
    # Get and validate API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Print error to console
        print(f"API Key Error: Please make sure OPENAI_API_KEY is set in your .env file.")
        raise ValueError("OpenAI API key not found.  Please make sure OPENAI_API_KEY is set in your .env file.")
    return ChatOpenAI(model=model_name, api_key=api_key)

def _get_ollama_model(model_name: str):
    # For Ollama, we use a base URL instead of an API key
    # Check if OLLAMA_HOST is set (for Docker on macOS)
    ollama_host = os.getenv("OLLAMA_HOST", "localhost")
    base_url = os.getenv("OLLAMA_BASE_URL", f"http://{ollama_host}:11434")
    return ChatOllama(
        model=model_name,
        base_url=base_url,
    )

MODEL_FACTORIES = {
    ModelProvider.ANTHROPIC: _get_anthropic_model,
    ModelProvider.DEEPSEEK: _get_deepseek_model,
    ModelProvider.GEMINI: _get_gemini_model,
    ModelProvider.GROQ: _get_groq_model,
    ModelProvider.OPENAI: _get_openai_model,
    ModelProvider.OLLAMA: _get_ollama_model,
}

def get_model(model_name: str, model_provider: ModelProvider) -> ChatOpenAI | ChatGroq | ChatOllama | ChatAnthropic | ChatDeepSeek | ChatGoogleGenerativeAI | None:
    factory = MODEL_FACTORIES.get(model_provider)
    if factory:
        try:
            return factory(model_name)
        except ValueError as e: # Catches API key errors specifically
            print(e) # The factory function already prints a detailed message
            return None # Or re-raise if you want the caller to handle it more explicitly

    print(f"Unsupported model provider: {model_provider}")
    return None
