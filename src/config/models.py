from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from typing import Literal

def get_chat_model(provider: Literal["openai", "groq"] = "openai", model: str = None):
    """
    Get the appropriate chat model based on provider and model name.
    
    Args:
        provider: The model provider ("openai" or "groq")
        model: Specific model name (optional)
        
    Raises:
        ValueError: If an invalid provider is specified
    """
    if provider == "groq":
        # Default to mixtral-8x7b-32768 for Groq if no model specified
        # llama2-70b-4096
        # gemma-7b-it
        model_name = model or "mixtral-8x7b-32768"
        return ChatGroq(
            model_name=model_name,
            temperature=0.7,
            max_tokens=1024,
        )
    elif provider == "openai":
        # Default to gpt-4 for OpenAI if no model specified
        model_name = model or "gpt-4"
        return ChatOpenAI(
            model_name=model_name,
            temperature=0.7,
        )
    else:
        raise ValueError(f"Invalid provider: {provider}. Must be one of: openai, groq")


