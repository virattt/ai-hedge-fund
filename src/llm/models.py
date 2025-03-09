import os
from enum import Enum
from typing import Tuple

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from pydantic import BaseModel


class ModelProvider(str, Enum):
    """Enum for supported LLM providers"""

    OPENAI = "OpenAI"
    GROQ = "Groq"
    ANTHROPIC = "Anthropic"
    GOOGLE = "Google"


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

    def is_gemini(self) -> bool:
        """Check if the model is a Gemini model"""
        return self.model_name.startswith("gemini")


# Define available models
AVAILABLE_MODELS = [
    LLMModel(display_name="[google] gemini-1.5-flash", model_name="gemini-1.5-flash", provider=ModelProvider.GOOGLE),
    LLMModel(
        display_name="[anthropic] claude-3.5-haiku",
        model_name="claude-3-5-haiku-latest",
        provider=ModelProvider.ANTHROPIC,
    ),
    LLMModel(
        display_name="[anthropic] claude-3.5-sonnet",
        model_name="claude-3-5-sonnet-latest",
        provider=ModelProvider.ANTHROPIC,
    ),
    LLMModel(
        display_name="[anthropic] claude-3.7-sonnet",
        model_name="claude-3-7-sonnet-latest",
        provider=ModelProvider.ANTHROPIC,
    ),
    LLMModel(
        display_name="[groq] deepseek-r1 70b", model_name="deepseek-r1-distill-llama-70b", provider=ModelProvider.GROQ
    ),
    LLMModel(display_name="[groq] llama-3.3 70b", model_name="llama-3.3-70b-versatile", provider=ModelProvider.GROQ),
    LLMModel(display_name="[openai] gpt-4o", model_name="gpt-4o", provider=ModelProvider.OPENAI),
    LLMModel(display_name="[openai] gpt-4o-mini", model_name="gpt-4o-mini", provider=ModelProvider.OPENAI),
    LLMModel(display_name="[openai] o1", model_name="o1", provider=ModelProvider.OPENAI),
    LLMModel(display_name="[openai] o3-mini", model_name="o3-mini", provider=ModelProvider.OPENAI),
]

# Create LLM_ORDER in the format expected by the UI
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]


def get_model_info(model_name: str) -> LLMModel | None:
    """Get model information by model_name"""
    return next((model for model in AVAILABLE_MODELS if model.model_name == model_name), None)


def get_model(
    model_name: str, model_provider: ModelProvider
) -> ChatOpenAI | ChatGroq | ChatAnthropic | ChatGoogleGenerativeAI | None:
    if model_provider == ModelProvider.GOOGLE:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("API Key Error: Please make sure GEMINI_API_KEY is set in your .env file.")
            raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")

        return ChatGoogleGenerativeAI(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.GROQ:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            # Print error to console
            print("API Key Error: Please make sure GROQ_API_KEY is set in your .env file.")
            raise ValueError("Groq API key not found.  Please make sure GROQ_API_KEY is set in your .env file.")
        return ChatGroq(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.OPENAI:
        # Get and validate API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Print error to console
            print("API Key Error: Please make sure OPENAI_API_KEY is set in your .env file.")
            raise ValueError("OpenAI API key not found.  Please make sure OPENAI_API_KEY is set in your .env file.")
        return ChatOpenAI(model=model_name, api_key=api_key)
    elif model_provider == ModelProvider.ANTHROPIC:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("API Key Error: Please make sure ANTHROPIC_API_KEY is set in your .env file.")
            raise ValueError(
                "Anthropic API key not found.  Please make sure ANTHROPIC_API_KEY is set in your .env file."
            )
        return ChatAnthropic(model=model_name, api_key=api_key)
