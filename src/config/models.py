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
        # Default to LLaMA2-70b-chat for Groq if no model specified
        model_name = model or "llama2-70b-chat"
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


