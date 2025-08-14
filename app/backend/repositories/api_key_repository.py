from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

from app.backend.database.models import ApiKey


class ApiKeyRepository:
    """Repository for API key database operations"""
    
    def __init__(self, db: Session):
        self.db = db

    def create_or_update_api_key(
        self, 
        provider: str, 
        key_value: str, 
        description: str = None, 
        is_active: bool = True
    ) -> ApiKey:
        """Create a new API key or update existing one"""
        # Check if API key already exists for this provider
        existing_key = self.db.query(ApiKey).filter(ApiKey.provider == provider).first()
        
        if existing_key:
            # Update existing key
            existing_key.key_value = key_value
            existing_key.description = description
            existing_key.is_active = is_active
            existing_key.updated_at = func.now()
            self.db.commit()
            self.db.refresh(existing_key)
            return existing_key
        else:
            # Create new key
            api_key = ApiKey(
                provider=provider,
                key_value=key_value,
                description=description,
                is_active=is_active
            )
            self.db.add(api_key)
            self.db.commit()
            self.db.refresh(api_key)
            return api_key

    def get_api_key_by_provider(self, provider: str) -> Optional[ApiKey]:
        """Get API key by provider name"""
        return self.db.query(ApiKey).filter(
            ApiKey.provider == provider,
            ApiKey.is_active == True
        ).first()

    def get_all_api_keys(self, include_inactive: bool = False) -> List[ApiKey]:
        """Get all API keys"""
        query = self.db.query(ApiKey)
        if not include_inactive:
            query = query.filter(ApiKey.is_active == True)
        return query.order_by(ApiKey.provider).all()

    def update_api_key(
        self, 
        provider: str, 
        key_value: str = None, 
        description: str = None, 
        is_active: bool = None
    ) -> Optional[ApiKey]:
        """Update an existing API key"""
        api_key = self.db.query(ApiKey).filter(ApiKey.provider == provider).first()
        if not api_key:
            return None

        if key_value is not None:
            api_key.key_value = key_value
        if description is not None:
            api_key.description = description
        if is_active is not None:
            api_key.is_active = is_active
        
        api_key.updated_at = func.now()
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def delete_api_key(self, provider: str) -> bool:
        """Delete an API key by provider"""
        api_key = self.db.query(ApiKey).filter(ApiKey.provider == provider).first()
        if not api_key:
            return False
        
        self.db.delete(api_key)
        self.db.commit()
        return True

    def deactivate_api_key(self, provider: str) -> bool:
        """Deactivate an API key instead of deleting it"""
        api_key = self.db.query(ApiKey).filter(ApiKey.provider == provider).first()
        if not api_key:
            return False
        
        api_key.is_active = False
        api_key.updated_at = func.now()
        self.db.commit()
        return True

    def update_last_used(self, provider: str) -> bool:
        """Update the last_used timestamp for an API key"""
        api_key = self.db.query(ApiKey).filter(
            ApiKey.provider == provider,
            ApiKey.is_active == True
        ).first()
        if not api_key:
            return False
        
        api_key.last_used = func.now()
        self.db.commit()
        return True

    def bulk_create_or_update(self, api_keys_data: List[dict]) -> List[ApiKey]:
        """Bulk create or update multiple API keys"""
        results = []
        for data in api_keys_data:
            api_key = self.create_or_update_api_key(
                provider=data['provider'],
                key_value=data['key_value'],
                description=data.get('description'),
                is_active=data.get('is_active', True)
            )
            results.append(api_key)
        return results 