from sqlalchemy.orm import Session
from typing import Dict, Optional
from app.backend.repositories.api_key_repository import ApiKeyRepository


class ApiKeyService:
    """Simple service to load API keys for requests"""
    
    def __init__(self, db: Session):
        self.repository = ApiKeyRepository(db)
    
    def get_api_keys_dict(self) -> Dict[str, str]:
        """
        Load all active API keys from database and return as a dictionary
        suitable for injecting into requests
        """
        api_keys = self.repository.get_all_api_keys(include_inactive=False)
        return {key.provider: key.key_value for key in api_keys}
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """Get a specific API key by provider"""
        api_key = self.repository.get_api_key_by_provider(provider)
        return api_key.key_value if api_key else None 