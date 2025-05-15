import os
import json
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from openai import OpenAI
from httpx import Client
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
    OPENROUTER = "OpenRouter"


class LLMModel(BaseModel):
    """Represents an LLM model configuration"""

    display_name: str
    model_name: str
    provider: ModelProvider
    api_base: str | None = None

    def to_choice_tuple(self) -> Tuple[str, str, str]:
        """Convert to format needed for questionary choices"""
        return (self.display_name, self.model_name, self.provider.value)

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

    def is_openrouter(self) -> bool:
        """Check if the model is an OpenRouter model"""
        return self.provider == ModelProvider.OPENROUTER


# Load models from JSON file
def load_models_from_json(json_path: str) -> List[LLMModel]:
    """Load models from a JSON file"""
    with open(json_path, 'r') as f:
        models_data = json.load(f)
    
    models = []
    for model_data in models_data:
        # Convert string provider to ModelProvider enum
        provider_enum = ModelProvider(model_data["provider"])
        models.append(
            LLMModel(
                display_name=model_data["display_name"],
                model_name=model_data["model_name"],
                provider=provider_enum,
                api_base=model_data.get("api_base")
            )
        )
    return models


# Get the path to the JSON files
current_dir = Path(__file__).parent
models_json_path = current_dir / "api_models.json"
ollama_models_json_path = current_dir / "ollama_models.json"

# Load available models from JSON
AVAILABLE_MODELS = load_models_from_json(str(models_json_path))

# Load Ollama models from JSON
OLLAMA_MODELS = load_models_from_json(str(ollama_models_json_path))

# Create LLM_ORDER in the format expected by the UI
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]

# Create Ollama LLM_ORDER separately
OLLAMA_LLM_ORDER = [model.to_choice_tuple() for model in OLLAMA_MODELS]


def get_model_info(model_name: str) -> LLMModel | None:
    """Get model information by model_name"""
    all_models = AVAILABLE_MODELS + OLLAMA_MODELS
    return next((model for model in all_models if model.model_name == model_name), None)


def get_model(model_name: str, model_provider: ModelProvider) -> ChatOpenAI | ChatGroq | ChatOllama | None:
    if model_provider == ModelProvider.GROQ:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure GROQ_API_KEY is set in your .env file.")
            raise ValueError("Groq API key not found.  Please make sure GROQ_API_KEY is set in your .env file.")
        return ChatGroq(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.OPENAI:
        # Get and validate API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure OPENAI_API_KEY is set in your .env file.")
            raise ValueError("OpenAI API key not found.  Please make sure OPENAI_API_KEY is set in your .env file.")
        return ChatOpenAI(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.ANTHROPIC:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure ANTHROPIC_API_KEY is set in your .env file.")
            raise ValueError("Anthropic API key not found.  Please make sure ANTHROPIC_API_KEY is set in your .env file.")
        return ChatAnthropic(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.DEEPSEEK:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure DEEPSEEK_API_KEY is set in your .env file.")
            raise ValueError("DeepSeek API key not found.  Please make sure DEEPSEEK_API_KEY is set in your .env file.")
        return ChatDeepSeek(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.GEMINI:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure GOOGLE_API_KEY is set in your .env file.")
            raise ValueError("Google API key not found.  Please make sure GOOGLE_API_KEY is set in your .env file.")
        return ChatGoogleGenerativeAI(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.OPENROUTER:
        # Use OpenRouter's API directly
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print(f"API Key Error: Please make sure OPENROUTER_API_KEY is set in your .env file.")
            raise ValueError("OpenRouter API key not found.  Please make sure OPENROUTER_API_KEY is set in your .env file.")
        model_info = get_model_info(model_name)
        if not model_info:
            raise ValueError(f"Model {model_name} not found in configuration")
            
        # Create a custom ChatOpenAI class that uses OpenRouter
        class ChatOpenRouter(ChatOpenAI):
            def __init__(self, model_name: str, api_key: str, api_base: str | None):
                super().__init__(
                    model=model_name,
                    api_key=api_key
                )
                if not api_base:
                    raise ValueError("API base URL is required for OpenRouter")
                
                # Ensure the base URL ends with a slash
                if not api_base.endswith('/'):
                    api_base += '/'
                
                # Create an HTTP client with proper headers
                self._http_client = Client(
                    base_url=api_base,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://your-app.com",
                        "X-Title": "HF"
                    },
                    timeout=30.0
                )
                
                # Configure OpenAI client with custom HTTP client
                self._client = OpenAI(
                    api_key=api_key,
                    base_url=api_base,
                    http_client=self._http_client
                )

            def invoke(self, prompt, stop=None, response_format=None, ls_structured_output_format=None):
                # Create a chat completion using OpenAI client with OpenRouter configuration
                messages = [{"role": "user", "content": prompt}]
                
                # If response_format is provided, add it to the messages
                if response_format:
                    messages[0]["content"] = "{}\n\nPlease respond in the following format:\n{}".format(prompt, response_format)
                
                # If ls_structured_output_format is provided, add it to the messages
                if ls_structured_output_format:
                    messages[0]["content"] = "{}\n\nPlease respond in the following structured format:\n{}".format(messages[0]["content"], ls_structured_output_format)
                
                response = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=messages
                )
                return response.choices[0].message.content

        return ChatOpenRouter(
            model_name=model_name,
            api_key=api_key,
            api_base=model_info.api_base
        )
    elif model_provider == ModelProvider.OLLAMA:
        # For Ollama, we use a base URL instead of an API key
        # Check if OLLAMA_HOST is set (for Docker on macOS)
        ollama_host = os.getenv("OLLAMA_HOST", "localhost")
        base_url = os.getenv("OLLAMA_BASE_URL", f"http://{ollama_host}:11434")
        return ChatOllama(
            model=model_name,
            base_url=base_url,
        )
