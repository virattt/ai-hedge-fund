import os
import logging
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)


async def get_dynamic_models() -> List[Dict[str, Any]]:
    """
    If OPENAI_API_BASE is set to a custom (non-OpenAI) endpoint, fetch its
    model list via the standard GET /v1/models endpoint and return them as
    OpenAI-provider models so they route through get_model() correctly.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE", "").rstrip("/")

    # Only activate when a custom base URL is explicitly configured
    if not api_key or not base_url or "api.openai.com" in base_url:
        return []

    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        logger.warning(
            f"OPENAI_API_BASE looks malformed (got: {base_url!r}). "
            "Make sure it starts with 'https://' in your .env file."
        )
        return []

    url = base_url + "/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        models = [
            {"display_name": item["id"], "model_name": item["id"], "provider": "OpenAI"}
            for item in data.get("data", [])
            if item.get("id")
        ]
        logger.info(f"[OpenAI custom base] Discovered {len(models)} models from {url}")
        return models
    except Exception as e:
        logger.warning(f"[OpenAI custom base] Failed to fetch models from {url}: {e}")

    # Fallback: use OPENAI_MODELS if the /models endpoint is not supported
    models_env = os.getenv("OPENAI_MODELS", "")
    if models_env:
        models = [
            {"display_name": m.strip(), "model_name": m.strip(), "provider": "OpenAI"}
            for m in models_env.split(",")
            if m.strip()
        ]
        logger.info(f"[OpenAI custom base] Using {len(models)} models from OPENAI_MODELS env var")
        return models

    return []
