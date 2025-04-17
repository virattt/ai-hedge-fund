import os
import requests
from datetime import datetime
from langchain_anthropic import ChatAnthropic
from langchain_deepseek import ChatDeepSeek
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from enum import Enum
from pydantic import BaseModel, field_validator, model_validator
from typing import Tuple, List, Dict, Any, Optional


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
    max_context: int = 128_000
    supports_function_calling: bool = False

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
    
    @field_validator("max_context")
    @classmethod
    def set_capabilities(cls, v, info):
        """Set model capabilities based on provider"""
        if info.data.get("provider") == ModelProvider.ANTHROPIC:
            return 200_000
        # Set specific context lengths for different models
        if info.data.get("model_name") == "gpt-4o":
            return 128_000
        if info.data.get("model_name") == "o1":
            return 128_000
        if "llama-4" in info.data.get("model_name", ""):
            return 128_000
        return v
    
    @model_validator(mode="after")
    def validate_model_name(self):
        """Validate model name is compatible with provider"""
        if self.provider == ModelProvider.OPENAI and "gpt-4.5" in self.model_name and not self.model_name == "gpt-4.5-preview":
            raise ValueError("GPT-4.5 is not a valid OpenAI model")
        
        # Set function calling support based on model
        if self.provider in [ModelProvider.OPENAI, ModelProvider.ANTHROPIC]:
            self.supports_function_calling = True
        elif self.provider == ModelProvider.GROQ and "llama-4" in self.model_name:
            self.supports_function_calling = True
            
        return self


class Price(BaseModel):
    """Model for price data with validation"""
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    @field_validator("time")
    @classmethod
    def validate_date(cls, v):
        """Validate price date is not too old"""
        try:
            if datetime.strptime(v, "%Y-%m-%d").year < 2000:
                raise ValueError("Date too far in past")
        except ValueError as e:
            if "does not match format" in str(e):
                raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD")
            raise
        return v


class Position(BaseModel):
    """Model for a portfolio position"""
    ticker: str
    shares: float
    average_cost: float


class Portfolio(BaseModel):
    """Model for a user's portfolio"""
    total_cash: float
    positions: Dict[str, Position]
    
    @property
    def total_value(self) -> float:
        """Calculate total portfolio value including cash and positions"""
        return self.total_cash + sum(
            pos.shares * get_current_price(pos.ticker)  # Requires price feed
            for pos in self.positions.values()
        )


# Define available models
AVAILABLE_MODELS = [
    LLMModel(
        display_name="[anthropic] claude-3.5-haiku",
        model_name="claude-3-5-haiku-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="[anthropic] claude-3.5-sonnet",
        model_name="claude-3-5-sonnet-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="[anthropic] claude-3.7-sonnet",
        model_name="claude-3-7-sonnet-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="[deepseek] deepseek-r1",
        model_name="deepseek-reasoner",
        provider=ModelProvider.DEEPSEEK
    ),
    LLMModel(
        display_name="[deepseek] deepseek-v3",
        model_name="deepseek-chat",
        provider=ModelProvider.DEEPSEEK
    ),
    LLMModel(
        display_name="[gemini] gemini-2.0-flash",
        model_name="gemini-2.0-flash",
        provider=ModelProvider.GEMINI
    ),
    LLMModel(
        display_name="[gemini] gemini-2.5-pro",
        model_name="gemini-2.5-pro-exp-03-25",
        provider=ModelProvider.GEMINI
    ),
    LLMModel(
        display_name="[groq] llama-4-scout-17b",
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
        provider=ModelProvider.GROQ
    ),
    LLMModel(
        display_name="[groq] llama-4-maverick-17b",
        model_name="meta-llama/llama-4-maverick-17b-128e-instruct",
        provider=ModelProvider.GROQ
    ),
    LLMModel(
        display_name="[openai] gpt-4.5",
        model_name="gpt-4.5-preview",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[openai] gpt-4o",
        model_name="gpt-4o",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[openai] o1",
        model_name="o1",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="[openai] o3-mini",
        model_name="o3-mini",
        provider=ModelProvider.OPENAI
    ),
]

# Define Ollama models separately
OLLAMA_MODELS = [
    LLMModel(
        display_name="[ollama] gemma3 (4B)",
        model_name="gemma3:4b",
        provider=ModelProvider.OLLAMA
    ),
    LLMModel(
        display_name="[ollama] qwen2.5 (7B)",
        model_name="qwen2.5",
        provider=ModelProvider.OLLAMA
    ),
    LLMModel(
        display_name="[ollama] llama3.1 (8B)",
        model_name="llama3.1:latest",
        provider=ModelProvider.OLLAMA
    ),
    LLMModel(
        display_name="[ollama] gemma3 (12B)",
        model_name="gemma3:12b",
        provider=ModelProvider.OLLAMA
    ),
    LLMModel(
        display_name="[ollama] mistral-small3.1 (24B)",
        model_name="mistral-small3.1",
        provider=ModelProvider.OLLAMA
    ),
    LLMModel(
        display_name="[ollama] gemma3 (27B)",
        model_name="gemma3:27b",
        provider=ModelProvider.OLLAMA
    ),
    LLMModel(
        display_name="[ollama] qwen2.5 (32B)",
        model_name="qwen2.5:32b",
        provider=ModelProvider.OLLAMA
    ),
    LLMModel(
        display_name="[ollama] llama-3.3 (70B)",
        model_name="llama3.3:70b-instruct-q4_0",
        provider=ModelProvider.OLLAMA
    ),
]

# Create LLM_ORDER in the format expected by the UI
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]

# Create Ollama LLM_ORDER separately
OLLAMA_LLM_ORDER = [model.to_choice_tuple() for model in OLLAMA_MODELS]


def get_current_price(ticker: str) -> float:
    """Get current price for a ticker from price feed"""
    # This is a placeholder function that would be implemented elsewhere
    # In a real implementation, this would fetch the current price from a data source
    return 0.0  # Placeholder


def get_model_info(model_name: str) -> Optional[LLMModel]:
    """Get model information by model_name"""
    all_models = AVAILABLE_MODELS + OLLAMA_MODELS
    return next((model for model in all_models if model.model_name == model_name), None)


def get_model(model_name: str, model_provider: ModelProvider):
    """
    Get a configured LLM instance based on model name and provider
    with improved error handling and health checks
    """
    # Check for missing API keys
    missing_keys = []
    
    if model_provider == ModelProvider.GROQ and not os.getenv("GROQ_API_KEY"):
        missing_keys.append("GROQ_API_KEY")
    elif model_provider == ModelProvider.OPENAI and not os.getenv("OPENAI_API_KEY"):
        missing_keys.append("OPENAI_API_KEY")
    elif model_provider == ModelProvider.ANTHROPIC and not os.getenv("ANTHROPIC_API_KEY"):
        missing_keys.append("ANTHROPIC_API_KEY")
    elif model_provider == ModelProvider.DEEPSEEK and not os.getenv("DEEPSEEK_API_KEY"):
        missing_keys.append("DEEPSEEK_API_KEY")
    elif model_provider == ModelProvider.GEMINI and not os.getenv("GOOGLE_API_KEY"):
        missing_keys.append("GOOGLE_API_KEY")
    
    if missing_keys:
        msg = f"Missing API keys: {', '.join(missing_keys)}"
        print(f"Error: {msg}")
        raise ValueError(msg)
    
    # Handle Ollama health check
    if model_provider == ModelProvider.OLLAMA:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            response = requests.get(f"{base_url}/api/tags")
            if response.status_code != 200:
                raise ConnectionError(f"Ollama server returned status code {response.status_code}")
            
            # Check if requested model is available
            models = [m["name"] for m in response.json().get("models", [])]
            if model_name not in models:
                raise ValueError(f"Model {model_name} not found in Ollama. Available models: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}")
                
            return ChatOllama(model=model_name, base_url=base_url)
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Ollama server not reachable at {base_url}")
    
    # Create model instances for other providers
    if model_provider == ModelProvider.GROQ:
        return ChatGroq(model=model_name, api_key=os.getenv("GROQ_API_KEY"))
    elif model_provider == ModelProvider.OPENAI:
        return ChatOpenAI(model=model_name, api_key=os.getenv("OPENAI_API_KEY"))
    elif model_provider == ModelProvider.ANTHROPIC:
        return ChatAnthropic(model=model_name, api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif model_provider == ModelProvider.DEEPSEEK:
        return ChatDeepSeek(model=model_name, api_key=os.getenv("DEEPSEEK_API_KEY"))
    elif model_provider == ModelProvider.GEMINI:
        return ChatGoogleGenerativeAI(model=model_name, api_key=os.getenv("GOOGLE_API_KEY"))