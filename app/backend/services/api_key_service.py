import os
from sqlalchemy.orm import Session
from typing import Dict, Optional
from app.backend.repositories.api_key_repository import ApiKeyRepository


# Known API key providers: env var name → human-readable description
_ENV_KEY_REGISTRY: Dict[str, str] = {
    "FINANCIAL_DATASETS_API_KEY": "Financial Datasets API",
    "OPENAI_API_KEY":             "OpenAI API",
    "ANTHROPIC_API_KEY":          "Anthropic API",
    "DEEPSEEK_API_KEY":           "DeepSeek API",
    "GROQ_API_KEY":               "Groq API",
    "GOOGLE_API_KEY":             "Google API",
    "XAI_API_KEY":                "xAI API",
    "MOONSHOT_API_KEY":           "Moonshot (Kimi) API",
    "GIGACHAT_API_KEY":           "GigaChat API",
    "OPENROUTER_API_KEY":         "OpenRouter API",
    "AZURE_OPENAI_API_KEY":       "Azure OpenAI API",
    "TENCENT_CODING_API_KEY":     "Tencent Coding Plan API",
    "TENCENT_MAAS_API_KEY":       "Tencent TokenHub MaaS API",
}

# Placeholder prefixes — values starting with these are not real keys
_PLACEHOLDER_PREFIXES = ("your-", "sk-your-", "sk-sp-your-")


def _is_placeholder(value: str) -> bool:
    """Return True if the value looks like a placeholder rather than a real key."""
    v = value.strip().lower()
    return any(v.startswith(p) for p in _PLACEHOLDER_PREFIXES)


class ApiKeyService:
    """Simple service to load API keys for requests"""

    def __init__(self, db: Session):
        self.repository = ApiKeyRepository(db)

    # ------------------------------------------------------------------
    # Startup helper
    # ------------------------------------------------------------------

    def sync_env_to_db(self) -> None:
        """
        One-time sync: write env-var values into the database for any
        provider that has a real (non-placeholder) value in the environment
        but no existing record in the database.

        DB values are never overwritten — if a user already saved a key
        via the UI it takes priority.
        """
        for env_var, description in _ENV_KEY_REGISTRY.items():
            value = os.getenv(env_var, "")
            if not value or _is_placeholder(value):
                continue
            # Only create if the DB doesn't have this provider yet
            existing = self.repository.get_api_key_by_provider(env_var)
            if existing is None:
                self.repository.create_or_update_api_key(
                    provider=env_var,
                    key_value=value,
                    description=description,
                    is_active=True,
                )

    # ------------------------------------------------------------------
    # Runtime helpers
    # ------------------------------------------------------------------

    def get_api_keys_dict(self) -> Dict[str, str]:
        """
        Return all active API keys as a dict {provider: key_value}.
        DB values take priority; env vars fill in anything the DB doesn't have.
        """
        db_keys = {key.provider: key.key_value
                   for key in self.repository.get_all_api_keys(include_inactive=False)}

        # Merge with env vars for providers not yet in DB
        for env_var in _ENV_KEY_REGISTRY:
            if env_var not in db_keys:
                value = os.getenv(env_var, "")
                if value and not _is_placeholder(value):
                    db_keys[env_var] = value

        return db_keys

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get a specific API key — DB first, then env var fallback."""
        db_key = self.repository.get_api_key_by_provider(provider)
        if db_key:
            return db_key.key_value
        # Fallback to env var
        value = os.getenv(provider, "")
        return value if value and not _is_placeholder(value) else None