"""Helper functions for LLM"""

import json
import logging
import time
from typing import Any

from pydantic import BaseModel
from src.llm.models import get_model, get_model_info
from src.utils.progress import progress
from src.graph.state import AgentState

# Configure logging
logger = logging.getLogger(__name__)


def call_llm(
    prompt: Any,
    pydantic_model: type[BaseModel],
    agent_name: str | None = None,
    state: AgentState | None = None,
    max_retries: int = 3,
    default_factory=None,
    temperature: float | None = None,
) -> BaseModel:
    """
    Makes an LLM call with retry logic and exponential backoff.
    
    Handles both JSON-supported and non-JSON-supported models, with automatic
    parsing and validation against the provided Pydantic model.

    Args:
        prompt: The prompt to send to the LLM
        pydantic_model: The Pydantic model class to structure the output
        agent_name: Optional name of the agent for progress updates and model config extraction
        state: Optional state object to extract agent-specific model configuration
        max_retries: Maximum number of retries (default: 3)
        default_factory: Optional factory function to create default response on failure
        temperature: Optional temperature override for the model (0.0-1.0)

    Returns:
        An instance of the specified Pydantic model
    """
    
    # Extract model configuration if state is provided and agent_name is available
    if state and agent_name:
        model_name, model_provider = get_agent_model_config(state, agent_name)
    else:
        # Use system defaults when no state or agent_name is provided
        model_name = "gpt-4.1"
        model_provider = "OPENAI"

    # Extract API keys from state if available
    api_keys = None
    if state:
        request = state.get("metadata", {}).get("request")
        if request and hasattr(request, 'api_keys'):
            api_keys = request.api_keys

    model_info = get_model_info(model_name, model_provider)
    llm = get_model(model_name, model_provider, api_keys)

    # For JSON-supporting models, use structured output
    if not (model_info and not model_info.has_json_mode()):
        llm = llm.with_structured_output(
            pydantic_model,
            method="json_mode",
        )

    # Call the LLM with retries and exponential backoff
    last_error = None
    for attempt in range(max_retries):
        try:
            # Call the LLM
            result = llm.invoke(prompt)

            # For non-JSON support models, we need to extract and parse the JSON manually
            if model_info and not model_info.has_json_mode():
                parsed_result = extract_json_from_response(result.content)
                if parsed_result:
                    return pydantic_model(**parsed_result)
                else:
                    raise ValueError("Failed to extract JSON from LLM response")
            else:
                return result

        except Exception as e:
            last_error = e
            
            # Calculate exponential backoff delay: 1s, 2s, 4s, ...
            delay = min(2 ** attempt, 10)  # Cap at 10 seconds
            
            if agent_name:
                progress.update_status(
                    agent_name, 
                    None, 
                    f"Error - retry {attempt + 1}/{max_retries} in {delay}s"
                )
            
            logger.warning(
                f"LLM call failed (attempt {attempt + 1}/{max_retries}): {e}. "
                f"Retrying in {delay}s..."
            )

            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                logger.error(f"LLM call failed after {max_retries} attempts: {last_error}")
                # Use default_factory if provided, otherwise create a basic default
                if default_factory:
                    return default_factory()
                return create_default_response(pydantic_model)

    # This should never be reached due to the retry logic above
    return create_default_response(pydantic_model)


def create_default_response(model_class: type[BaseModel]) -> BaseModel:
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


def extract_json_from_response(content: str) -> dict | None:
    """
    Extracts JSON from LLM response, handling multiple formats.
    
    Supports:
    - JSON wrapped in ```json ... ``` code blocks
    - JSON wrapped in ``` ... ``` code blocks
    - Raw JSON without code blocks
    - JSON with leading/trailing text
    
    Args:
        content: The raw string response from the LLM
        
    Returns:
        Parsed JSON as a dictionary, or None if parsing fails
    """
    if not content:
        return None
        
    content = content.strip()
    
    # Try 1: Extract from ```json code block
    try:
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7:]
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    
    # Try 2: Extract from ``` code block (no language specified)
    try:
        json_start = content.find("```")
        if json_start != -1:
            json_text = content[json_start + 3:]
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                # Skip language identifier if present on first line
                if json_text and not json_text.startswith('{'):
                    first_newline = json_text.find('\n')
                    if first_newline != -1:
                        json_text = json_text[first_newline:].strip()
                return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    
    # Try 3: Parse the entire content as JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try 4: Find JSON object boundaries { ... }
    try:
        start = content.find('{')
        if start != -1:
            # Find matching closing brace
            brace_count = 0
            for i, char in enumerate(content[start:], start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_text = content[start:i+1]
                        return json.loads(json_text)
    except json.JSONDecodeError:
        pass
    
    logger.warning(f"Failed to extract JSON from response: {content[:200]}...")
    return None


def get_agent_model_config(state, agent_name):
    """
    Get model configuration for a specific agent from the state.
    Falls back to global model configuration if agent-specific config is not available.
    Always returns valid model_name and model_provider values.
    """
    request = state.get("metadata", {}).get("request")
    
    if request and hasattr(request, 'get_agent_model_config'):
        # Get agent-specific model configuration
        model_name, model_provider = request.get_agent_model_config(agent_name)
        # Ensure we have valid values
        if model_name and model_provider:
            return model_name, model_provider.value if hasattr(model_provider, 'value') else str(model_provider)
    
    # Fall back to global configuration (system defaults)
    model_name = state.get("metadata", {}).get("model_name") or "gpt-4.1"
    model_provider = state.get("metadata", {}).get("model_provider") or "OPENAI"
    
    # Convert enum to string if necessary
    if hasattr(model_provider, 'value'):
        model_provider = model_provider.value
    
    return model_name, model_provider
