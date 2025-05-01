"""Helper functions for LLM API interactions with improved error handling and type safety."""

import json
import time
import functools
import logging
from threading import Lock
from typing import TypeVar, Type, Optional, Dict, Any, Union, Callable, cast
from pydantic import BaseModel, ValidationError
from json.decoder import JSONDecodeError
from utils.progress import get_progress

# Setup logging
logger = logging.getLogger(__name__)

# Type for Pydantic models
T = TypeVar('T', bound=BaseModel)

# Cache for initialized models to avoid repeated initialization
_MODEL_CACHE: Dict[str, Any] = {}
_MODEL_CACHE_LOCK = Lock()

# Rate limiting tracker
_LAST_CALL_TIME: Dict[str, float] = {}
_RATE_LIMIT_LOCK = Lock()

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass

class JSONParsingError(LLMError):
    """Exception raised when JSON parsing fails."""
    pass

class ModelNotAvailableError(LLMError):
    """Exception raised when a model is not available."""
    pass

class RateLimitError(LLMError):
    """Exception raised when rate limits are hit."""
    pass

def rate_limit(min_interval: float = 0.5):
    """Decorator to enforce rate limiting between API calls.
    
    Args:
        min_interval: Minimum time between calls in seconds
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            model_key = f"{kwargs.get('model_provider', 'default')}:{kwargs.get('model_name', 'default')}"
            
            with _RATE_LIMIT_LOCK:
                current_time = time.time()
                last_call = _LAST_CALL_TIME.get(model_key, 0)
                time_since_last_call = current_time - last_call
                
                if time_since_last_call < min_interval:
                    sleep_time = min_interval - time_since_last_call
                    time.sleep(sleep_time)
                
                _LAST_CALL_TIME[model_key] = time.time()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit()
def call_llm(
    prompt: Union[str, Dict[str, Any]],
    model_name: str,
    model_provider: str,
    pydantic_model: Type[T],
    agent_name: Optional[str] = None,
    max_retries: int = 3,
    default_factory: Optional[Callable[[], T]] = None,
    timeout: float = 30.0
) -> T:
    """
    Makes an LLM call with robust retry logic and error handling.
    
    Args:
        prompt: The prompt to send to the LLM (string or structured prompt)
        model_name: Name of the model to use
        model_provider: Provider of the model
        pydantic_model: The Pydantic model class to structure the output
        agent_name: Optional name of the agent for progress updates
        max_retries: Maximum number of retries (default: 3)
        default_factory: Optional factory function to create default response on failure
        timeout: Timeout for the LLM call in seconds
        
    Returns:
        An instance of the specified Pydantic model
        
    Raises:
        ModelNotAvailableError: If the model cannot be initialized
        RateLimitError: If rate limits are exceeded even after retries
        LLMError: For other LLM-related errors
    """
    from llm.models import get_model, get_model_info
    
    progress = get_progress()
    
    # Get model info
    try:
        model_info = get_model_info(model_name)
        if not model_info:
            raise ModelNotAvailableError(f"Model info not available for {model_name}")
    except Exception as e:
        logger.error(f"Error getting model info for {model_name}: {e}")
        if agent_name:
            progress.update_status(agent_name, None, f"Error: Model info unavailable")
        raise ModelNotAvailableError(f"Could not get model info: {str(e)}")
    
    # Get or initialize the model
    try:
        cache_key = f"{model_provider}:{model_name}"
        with _MODEL_CACHE_LOCK:
            if cache_key not in _MODEL_CACHE:
                llm = get_model(model_name, model_provider)
                _MODEL_CACHE[cache_key] = llm
            else:
                llm = _MODEL_CACHE[cache_key]
    except Exception as e:
        logger.error(f"Error initializing model {model_name} from {model_provider}: {e}")
        if agent_name:
            progress.update_status(agent_name, None, f"Error: Model initialization failed")
        raise ModelNotAvailableError(f"Could not initialize model: {str(e)}")
    
    # For models with JSON support, use structured output
    has_json_mode = model_info.has_json_mode() if model_info else False
    if has_json_mode:
        llm = llm.with_structured_output(
            pydantic_model,
            method="json_mode",
        )
    
    # Call the LLM with retries
    backoff_factor = 1.5
    wait_time = 1.0
    
    for attempt in range(max_retries):
        try:
            if agent_name:
                status = "Processing" if attempt == 0 else f"Retry {attempt}/{max_retries}"
                progress.update_status(agent_name, None, status)
            
            # Invoke the model with timeout
            result = llm.invoke(
                prompt,
                config={"timeout": timeout}
            )
            
            # For non-JSON support models, extract and parse JSON manually
            if not has_json_mode:
                try:
                    parsed_result = extract_json_from_response(result.content)
                    if parsed_result:
                        # Validate against the model
                        return validate_model(pydantic_model, parsed_result)
                    else:
                        raise JSONParsingError("Failed to extract JSON from response")
                except JSONDecodeError as je:
                    logger.warning(f"JSON decode error on attempt {attempt+1}: {je}")
                    if attempt < max_retries - 1:
                        continue
                    raise JSONParsingError(f"Failed to parse JSON: {je}")
            else:
                # For JSON-mode models, result should already be the model instance
                return cast(T, result)
                
        except RateLimitError as rle:
            logger.warning(f"Rate limit hit on attempt {attempt+1}: {rle}")
            if agent_name:
                progress.update_status(agent_name, None, f"Rate limit - waiting")
            
            # Exponential backoff
            if attempt < max_retries - 1:
                time.sleep(wait_time)
                wait_time *= backoff_factor
            else:
                raise
                
        except (JSONParsingError, ValidationError) as ve:
            logger.warning(f"Validation error on attempt {attempt+1}: {ve}")
            if agent_name:
                progress.update_status(agent_name, None, f"Format error - retry {attempt+1}/{max_retries}")
            
            if attempt < max_retries - 1:
                continue
            else:
                # For the last attempt, try the default factory
                break
                
        except Exception as e:
            logger.error(f"Error in LLM call (attempt {attempt+1}): {e}")
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt+1}/{max_retries}")
            
            if attempt < max_retries - 1:
                time.sleep(wait_time)
                wait_time *= backoff_factor
            else:
                break

    # If we get here, all attempts failed
    if agent_name:
        progress.update_status(agent_name, None, "Error - using default")
    
    logger.error(f"All {max_retries} attempts failed for {model_name} call")
    
    # Use default_factory if provided, otherwise create a basic default
    if default_factory:
        return default_factory()
    return create_default_response(pydantic_model)

def validate_model(model_class: Type[T], data: dict) -> T:
    """
    Validates data against a Pydantic model with improved error handling.
    
    Args:
        model_class: The Pydantic model class
        data: Dictionary of data to validate
        
    Returns:
        Validated model instance
        
    Raises:
        ValidationError: If validation fails
    """
    try:
        return model_class(**data)
    except ValidationError as e:
        # Try to fix common issues
        fixed_data = data.copy()
        
        # Look through validation errors for missing fields and add defaults
        for err in e.errors():
            if err["type"] == "missing":
                field_name = err["loc"][0]
                if field_name in model_class.model_fields:
                    field = model_class.model_fields[field_name]
                    if field.default is not None:
                        fixed_data[field_name] = field.default
        
        # Try again with fixed data
        try:
            return model_class(**fixed_data)
        except ValidationError:
            # If still failing, re-raise the original error
            raise e

def create_default_response(model_class: Type[T]) -> T:
    """
    Creates a safe default response based on the model's fields.
    
    Args:
        model_class: The Pydantic model class
        
    Returns:
        A default instance of the model
    """
    default_values = {}
    
    for field_name, field in model_class.model_fields.items():
        field_type = field.annotation
        
        # Handle string fields
        if field_type == str or field_type == Optional[str]:
            default_values[field_name] = "Error in analysis, using default"
        
        # Handle numeric fields
        elif field_type == float or field_type == Optional[float]:
            default_values[field_name] = 0.0
        elif field_type == int or field_type == Optional[int]:
            default_values[field_name] = 0
        
        # Handle container types
        elif hasattr(field_type, "__origin__"):
            origin = field_type.__origin__
            if origin == dict:
                default_values[field_name] = {}
            elif origin == list:
                default_values[field_name] = []
            elif origin == Union:
                # For Optional fields (Union[X, None])
                if type(None) in field_type.__args__:
                    default_values[field_name] = None
                else:
                    # Try to use the first non-None type
                    for arg in field_type.__args__:
                        if arg is not type(None):
                            if arg == str:
                                default_values[field_name] = "Error in analysis, using default"
                            elif arg == int:
                                default_values[field_name] = 0
                            elif arg == float:
                                default_values[field_name] = 0.0
                            elif arg == bool:
                                default_values[field_name] = False
                            elif arg == dict:
                                default_values[field_name] = {}
                            elif arg == list:
                                default_values[field_name] = []
                            else:
                                default_values[field_name] = None
                            break
        
        # Handle enumeration types
        elif hasattr(field_type, "__args__"):
            # For Literal or Enum types, use the first value
            default_values[field_name] = field_type.__args__[0]
        
        # Handle nested models
        elif isinstance(field_type, type) and issubclass(field_type, BaseModel):
            default_values[field_name] = create_default_response(field_type)
        
        # Fall back to None for unknown types
        else:
            default_values[field_name] = None
    
    # Create and return the model instance
    return model_class(**default_values)

def extract_json_from_response(content: str) -> Optional[dict]:
    """
    Extracts JSON from markdown-formatted response with multiple fallback strategies.
    
    Args:
        content: The raw response content from the LLM
        
    Returns:
        Extracted JSON as a dictionary, or None if extraction fails
        
    Raises:
        JSONDecodeError: If JSON parsing fails after extraction
    """
    if not content:
        return None
    
    # Strategy 1: Look for ```json code blocks
    try:
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7:]  # Skip past ```json
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except Exception:
        # Continue to next strategy
        pass
    
    # Strategy 2: Look for regular ``` code blocks that might contain JSON
    try:
        json_start = content.find("```")
        if json_start != -1:
            # Skip the opening ```
            json_text = content[json_start + 3:]
            # Look for language identifier
            if json_text.startswith("json"):
                json_text = json_text[4:]  # Skip past "json"
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except Exception:
        # Continue to next strategy
        pass
    
    # Strategy 3: Look for JSON-like structures using { } as delimiters
    try:
        first_brace = content.find("{")
        if first_brace != -1:
            # Count braces to find matching close
            brace_count = 1
            for i in range(first_brace + 1, len(content)):
                if content[i] == "{":
                    brace_count += 1
                elif content[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        # We found the matching closing brace
                        json_text = content[first_brace : i + 1]
                        return json.loads(json_text)
    except Exception:
        # Continue to next strategy
        pass
    
    # Strategy 4: Desperate attempt - try to parse the whole text as JSON
    try:
        return json.loads(content)
    except Exception as e:
        logger.warning(f"All JSON extraction strategies failed: {e}")
        return None

# Async versions of the functions could be added here for concurrent processing