"""Helper functions for LLM"""

import json
from typing import TypeVar, Type, Optional, Any
from pydantic import BaseModel
from utils.progress import progress
from langchain_core.output_parsers import PydanticOutputParser

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
    Makes an LLM call with retry logic, handling different model types appropriately.
    
    Args:
        prompt: The prompt to send to the LLM
        model_name: Name of the model to use
        model_provider: Provider of the model
        pydantic_model: The Pydantic model class to structure the output
        agent_name: Optional name of the agent for progress updates
        max_retries: Maximum number of retries (default: 3)
        default_factory: Optional factory function to create default response on failure
        
    Returns:
        An instance of the specified Pydantic model
    """
    from llm.models import get_model, get_model_info
    
    model_info = get_model_info(model_name)
    llm = get_model(model_name, model_provider)
    
    # Create a parser for models that don't support structured output natively
    parser = PydanticOutputParser(pydantic_object=pydantic_model)
    
    # Call the LLM with retries
    for attempt in range(max_retries):
        try:
            # For models that support structured output directly
            if hasattr(llm, "with_structured_output") and not (model_info and model_info.is_deepseek()):
                try:
                    structured_llm = llm.with_structured_output(
                        pydantic_model,
                        method="json_mode",
                    )
                    return structured_llm.invoke(prompt)
                except (NotImplementedError, AttributeError):
                    # Fall back to manual parsing if structured output fails
                    pass
            
            # For Ollama (Mistral) and other models without native structured output support
            formatted_prompt = f"{prompt}\n\nYou must respond with a valid JSON object that conforms to this Pydantic model:\n{parser.get_format_instructions()}"
            result = llm.invoke(formatted_prompt)
            content = result.content if hasattr(result, "content") else str(result)
            
            # For Deepseek, extract JSON from markdown
            if model_info and model_info.is_deepseek():
                parsed_result = extract_json_from_deepseek_response(content)
                if parsed_result:
                    return pydantic_model(**parsed_result)
            
            # For Ollama and other models, try to parse the response
            try:
                # Try direct parsing first
                return parser.parse(content)
            except Exception:
                # If that fails, try to extract JSON from the response
                parsed_result = extract_json_from_response(content)
                if parsed_result:
                    return pydantic_model(**parsed_result)
                raise
                
        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}")
            
            if attempt == max_retries - 1:
                print(f"Error in LLM call after {max_retries} attempts: {e}")
                # Use default_factory if provided, otherwise create a basic default
                if default_factory:
                    return default_factory()
                return create_default_response(pydantic_model)

    # This should never be reached due to the retry logic above
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

def extract_json_from_response(content: str) -> Optional[dict]:
    """Extracts JSON from any text response by looking for JSON-like structures."""
    try:
        # Try to find JSON enclosed in code blocks
        for marker in ["```json", "```"]:
            json_start = content.find(marker)
            if json_start != -1:
                json_text = content[json_start + len(marker):]
                json_end = json_text.find("```")
                if json_end != -1:
                    json_text = json_text[:json_end].strip()
                    return json.loads(json_text)
        
        # Look for JSON objects starting with { and ending with }
        brace_start = content.find("{")
        if brace_start != -1:
            # Find the matching closing brace
            brace_count = 0
            for i in range(brace_start, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return json.loads(content[brace_start:i+1])
        
        # As a last resort, try to parse the entire response as JSON
        return json.loads(content)
    except Exception as e:
        print(f"Error extracting JSON from response: {e}")
    return None