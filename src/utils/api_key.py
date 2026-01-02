

def get_api_key_from_state(state: dict, api_key_name: str) -> str:
    """Get an API key from the state object."""
    if state and state.get("metadata", {}).get("request"):
        request = state["metadata"]["request"]
        if hasattr(request, 'api_keys') and request.api_keys:
            return request.api_keys.get(api_key_name)
    return None