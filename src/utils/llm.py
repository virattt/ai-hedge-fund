"""Helper functions for LLM"""

import json
from typing import TypeVar, Type, Optional, Any
from pydantic import BaseModel
from utils.progress import progress
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq

T = TypeVar('T', bound=BaseModel)

def get_llm(provider: str, model_name: str):
    """Get LLM instance based on provider and model name"""
    provider = provider.lower()
    if provider == "google":
        return ChatGoogleGenerativeAI(model=model_name)
    elif provider == "openai":
        return ChatOpenAI(model=model_name)
    elif provider == "anthropic":
        return ChatAnthropic(model=model_name)
    elif provider == "groq":
        return ChatGroq(model=model_name)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

def call_llm(
    llm,
    prompt: str,
    output_schema: Type[BaseModel],
    **kwargs
) -> Any:
    """Call LLM with structured output"""
    result = None
    
    try:
        # For Google models, we'll use a different approach
        if isinstance(llm, ChatGoogleGenerativeAI):
            # First get raw response
            result = llm.invoke(prompt)
            
            # If we already got a Pydantic model of the right type, return it
            if isinstance(result, output_schema):
                return result
                
            # Extract JSON from AIMessage if needed
            if hasattr(result, 'content'):
                # Try to extract JSON from markdown code blocks first
                json_data = extract_json_from_deepseek_response(result.content)
                if json_data:
                    result = json_data
                else:
                    # If no code blocks, try the content directly
                    try:
                        result = json.loads(result.content)
                    except json.JSONDecodeError:
                        return create_default_response(output_schema)
            
            # For PortfolioManagerOutput, we need special handling
            if output_schema.__name__ == "PortfolioManagerOutput":
                from agents.portfolio_manager import PortfolioDecision
                
                # Get the decisions data
                if isinstance(result, dict):
                    decisions_data = result.get("decisions", result)
                else:
                    return create_default_response(output_schema)
                
                # Convert each decision to a PortfolioDecision object
                processed_decisions = {}
                for ticker, decision in decisions_data.items():
                    try:
                        if isinstance(decision, str):
                            decision = json.loads(decision)
                        processed_decisions[ticker] = PortfolioDecision(**decision)
                    except Exception as e:
                        return create_default_response(output_schema)
                
                return output_schema(decisions=processed_decisions)
            
            # For other schemas, try direct validation
            return output_schema.model_validate(result)
        else:
            # For other providers (OpenAI, Anthropic, etc) use json_mode
            llm = llm.with_structured_output(output_schema, method="json_mode")
            return llm.invoke(prompt)
            
    except Exception as e:
        return create_default_response(output_schema)

def create_default_response(model_class: Type[T]) -> T:
    """Creates a safe default response based on the model's fields."""
    default_values = {}
    for field_name, field in model_class.model_fields.items():
        if field.annotation == str:
            default_values[field_name] = "Error in analysis, using default"
        elif field.annotation == float:
            default_values[field_name] = 0.0
        elif field.annotation == int:
            default_values[field_name] = 0
        elif hasattr(field.annotation, "__origin__") and field.annotation.__origin__ == dict:
            default_values[field_name] = {}
        else:
            # For other types (like Literal), try to use the first allowed value
            if hasattr(field.annotation, "__args__"):
                default_values[field_name] = field.annotation.__args__[0]
            else:
                default_values[field_name] = None
    
    return model_class(**default_values)

def extract_json_from_deepseek_response(content: str) -> Optional[dict]:
    """Extracts JSON from Deepseek's markdown-formatted response."""
    try:
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7:]  # Skip past ```json
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except Exception as e:
        print(f"Error extracting JSON from Deepseek response: {e}")
    return None
