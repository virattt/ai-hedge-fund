"""Helper functions for LLM"""

import json
from typing import TypeVar, Type, Optional, Any
from pydantic import BaseModel
from utils.progress import progress

T = TypeVar('T', bound=BaseModel)

def map_signal_to_action(signal: str) -> str:
    """Maps sentiment/signal words to valid portfolio actions"""
    signal = signal.lower().strip()
    if signal in ("bearish", "negative", "sell signal"):
        return "sell"
    elif signal in ("bullish", "positive", "buy signal"):
        return "buy"
    elif signal in ("neutral", "sideways"):
        return "hold"
    return signal  # return as-is if already a valid action

def clean_json_response(data: dict) -> dict:
    """Clean and validate JSON response data"""
    if "decisions" in data:
        for ticker, decision in data["decisions"].items():
            if "action" in decision:
                decision["action"] = map_signal_to_action(decision["action"])
    return data

T = TypeVar('T', bound=BaseModel)

def call_llm(
    prompt: Any,
    model_name: str,
    model_provider: str,
    pydantic_model: Type[T],
    agent_name: Optional[str] = None,
    max_retries: int = 3,
    default_factory = None
) -> T:
    """
    Makes an LLM call with retry logic, handling different model providers.
    """
    from llm.models import get_model, get_model_info
    
    model_info = get_model_info(model_name)
    llm = get_model(model_name, model_provider)
    
    needs_manual_parsing = model_info and (model_info.is_deepseek() or model_provider.lower() == 'google')
    
    # For models that support structured output
    if not needs_manual_parsing:
        llm = llm.with_structured_output(
            pydantic_model,
            method="json_mode",
        )
    
    # Call the LLM with retries
    for attempt in range(max_retries):
        try:
            # Call the LLM
            result = llm.invoke(prompt)
            
            # For models needing manual JSON parsing
            if needs_manual_parsing:
                if model_info.is_deepseek():
                    parsed_result = extract_json_from_deepseek_response(result.content)
                else:  # Google model
                    parsed_result = extract_json_from_google_response(result.content)
                    
                if parsed_result:
                    return pydantic_model(**parsed_result)
            else:
                return result
                
        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}")
            
            if attempt == max_retries - 1:
                print(f"Error in LLM call after {max_retries} attempts: {e}")
                if default_factory:
                    return default_factory()
                return create_default_response(pydantic_model)

    return create_default_response(pydantic_model)

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

def extract_json_from_google_response(content: str) -> Optional[dict]:
    """Extracts JSON from Google model's response."""
    try:
        # First try to parse the entire content as JSON
        try:
            data = json.loads(content)
            return clean_json_response(data)
        except:
            pass
            
        # Look for JSON-like content within markdown blocks
        json_start = content.find("```")
        if json_start != -1:
            json_text = content[json_start + 3:]
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                # Remove any language identifier if present
                if json_text.startswith("json"):
                    json_text = json_text[4:].strip()
                data = json.loads(json_text)
                return clean_json_response(data)
                
        # Try to find JSON-like content between curly braces
        start_idx = content.find("{")
        if start_idx != -1:
            # Find matching closing brace
            count = 1
            for i in range(start_idx + 1, len(content)):
                if content[i] == "{":
                    count += 1
                elif content[i] == "}":
                    count -= 1
                if count == 0:
                    json_text = content[start_idx:i + 1]
                    data = json.loads(json_text)
                    return clean_json_response(data)
                    
    except Exception as e:
        print(f"Error extracting JSON from Google response: {e}")
    return None
