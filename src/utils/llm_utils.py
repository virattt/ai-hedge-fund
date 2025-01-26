import re
import json
from typing import Optional, TypeVar, Generic
from pydantic import BaseModel

T = TypeVar('T')

def parse_llm_response(result, output_model: type[T]) -> Optional[T]:
    """
    Parses a JSON response from an LLM into a Pydantic model
    
    Args:
        result: Raw LLM response containing a JSON block
        output_model: Pydantic model class to parse the response into
    
    Returns:
        Parsed model instance or None if parsing fails
    """
    try:
        # Extract JSON block from the raw response
        json_match = re.search(r'```json\s*(\{.*\})\s*```', result.content, re.DOTALL)
        
        if json_match:
            json_str = json_match.group(1)
            parsed_result = json.loads(json_str)
            
            # Convert to provided model format
            return output_model(**parsed_result)
        else:
            print("No valid JSON block found in the response.")
            print("Raw response:", result.content)
            return None     
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {str(e)}")
        print("Raw response:", result.content)
        return None
    except Exception as e:
        print(f"Error parsing response: {str(e)}")
        return None 