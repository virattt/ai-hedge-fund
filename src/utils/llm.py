"""Helper functions for LLM"""

import json
from typing import TypeVar, Type, Optional, Any
from pydantic import BaseModel
from src.llm.models import get_model, get_model_info, ModelProvider
from src.utils.progress import progress

T = TypeVar("T", bound=BaseModel)


def call_llm(
    prompt: Any,
    model_name: str,
    model_provider: str,
    pydantic_model: Type[T],
    agent_name: Optional[str] = None,
    max_retries: int = 3,
    default_factory=None,
) -> T:
    """
    Makes an LLM call with retry logic, handling both JSON supported and non-JSON supported models.

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

    model_info = get_model_info(model_name, model_provider)  # model_provider es str aquí

    # Convert model_provider string to ModelProvider enum for get_model
    try:
        # Aseguramos que model_provider sea el valor string del enum ModelProvider
        provider_enum = ModelProvider(model_provider)
    except ValueError:
        print(f"Invalid model provider string: {model_provider}")
        if default_factory:
            return default_factory()
        return create_default_response(pydantic_model)

    llm = get_model(model_name, provider_enum)

    if not llm:
        # get_model ya imprime un error si la API key falta o el proveedor no es soportado
        # print(f"Could not get LLM for {model_name} from {provider_enum.value}")
        if default_factory:
            return default_factory()
        return create_default_response(pydantic_model)

    # Use structured output if the model supports JSON mode
    # model_info es una instancia de LLMModel y tiene el método has_json_mode()
    if model_info and model_info.has_json_mode():
        llm = llm.with_structured_output(
            pydantic_model,
            method="json_mode",
        )

    # Call the LLM with retries
    for attempt in range(max_retries):
        try:
            # Call the LLM
            result = llm.invoke(prompt)

            # For models that don't natively support JSON mode but are expected to return JSON in content
            if model_info and not model_info.has_json_mode():
                # Ensure result has 'content' attribute (e.g. AIMessage)
                if hasattr(result, 'content') and isinstance(result.content, str):
                    parsed_result = extract_json_from_response(result.content)
                    if parsed_result:
                        return pydantic_model(**parsed_result)
                    else:
                        # Content was not valid JSON or not in expected format
                        error_message = f"Could not parse JSON from non-JSON mode model response for {model_name} (attempt {attempt + 1})"
                        print(error_message)
                        if attempt == max_retries - 1:  # Last attempt
                            raise ValueError(error_message)
                        # Continue to next retry if not last attempt
                else:
                    # Response format unexpected for manual JSON parsing
                    error_message = f"Unexpected response format for manual JSON parsing from {model_name} (attempt {attempt + 1})"
                    print(error_message)
                    if attempt == max_retries - 1:
                        raise TypeError(error_message)
            else:  # Model supports JSON mode (or result is already the pydantic model)
                if isinstance(result, pydantic_model):
                    return result
                else:
                    # Esto no debería ocurrir si with_structured_output funciona como se espera
                    # o si el modelo sin json_mode devuelve un AIMessage.
                    # Podría ser un error en la lógica o un tipo de respuesta inesperado.
                    error_message = f"Unexpected result type from LLM: {type(result)}. Expected {pydantic_model.__name__}."
                    print(error_message)
                    if attempt == max_retries - 1:
                        raise TypeError(error_message)

        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}: {str(e)[:100]}")

            if attempt == max_retries - 1:
                print(f"Error in LLM call to {model_name} ({provider_enum.value}) after {max_retries} attempts: {e}")
                if default_factory:
                    return default_factory()
                return create_default_response(pydantic_model)

    # Fallback si el bucle termina sin return (no debería con el raise en el último intento)
    print(f"LLM call failed definitively for {model_name} ({provider_enum.value}). Returning default.")
    if default_factory:
        return default_factory()
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


def extract_json_from_response(content: str) -> Optional[dict]:
    """Extracts JSON from markdown-formatted response."""
    try:
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7 :]  # Skip past ```json
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except Exception as e:
        print(f"Error extracting JSON from response: {e}")
    return None
