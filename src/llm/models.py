import os
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from enum import Enum
from pydantic import BaseModel
from typing import Tuple


class ModelProvider(str, Enum):
    """Enum for supported LLM providers"""
    OPENAI = "OpenAI"
    GROQ = "Groq"
    ANTHROPIC = "Anthropic"


class LLMModel(BaseModel):
    """Represents an LLM model configuration"""
    display_name: str
    model_name: str
    provider: ModelProvider

    def to_choice_tuple(self) -> Tuple[str, str, str]:
        """Convert to format needed for questionary choices"""
        return (self.display_name, self.model_name, self.provider.value)
    
    def is_deepseek(self) -> bool:
        """Check if the model is a DeepSeek model"""
        return self.model_name.startswith("deepseek")


# Define available models
AVAILABLE_MODELS = [
    LLMModel(
        display_name="gpt-4o [openai]",
        model_name="gpt-4o",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="gpt-4o-mini [openai]",
        model_name="gpt-4o-mini",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="o3-mini [openai]",
        model_name="o3-mini",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="deepseek-r1 70b [groq]",
        model_name="deepseek-r1-distill-llama-70b",
        provider=ModelProvider.GROQ
    ),
    LLMModel(
        display_name="llama-3.3 70b [groq]",
        model_name="llama-3.3-70b-versatile",
        provider=ModelProvider.GROQ
    ),
    LLMModel(
        display_name="claude-3.5-sonnet [anthropic]",
        model_name="claude-3-5-sonnet-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="claude-3.5-haiku [anthropic]",
        model_name="claude-3-5-haiku-latest",
        provider=ModelProvider.ANTHROPIC
    ),
    LLMModel(
        display_name="claude-3-opus [anthropic]",
        model_name="claude-3-opus-latest",
        provider=ModelProvider.ANTHROPIC
    ),
]

# Create LLM_ORDER in the format expected by the UI
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]

def get_model_info(model_name: str) -> LLMModel | None:
    """Get model information by model_name"""
    return next((model for model in AVAILABLE_MODELS if model.model_name == model_name), None)

def get_model(model_name: str, model_provider: ModelProvider) -> ChatOpenAI | ChatGroq | None:
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