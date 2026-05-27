use sqlx::SqlitePool;
use std::collections::HashMap;
use anyhow::Result;
use crate::repositories::api_key_repository::ApiKeyRepository;

pub struct ApiKeyService<'a> {
    pub db: &'a SqlitePool,
}

impl<'a> ApiKeyService<'a> {
    pub fn new(db: &'a SqlitePool) -> Self {
        Self { db }
    }

    pub async fn get_api_keys_dict(&self) -> Result<HashMap<String, String>> {
        let repo = ApiKeyRepository::new(self.db);
        let api_keys = repo.get_all_api_keys(false).await?;
        let mut keys_map = HashMap::new();
        for key in api_keys {
            keys_map.insert(key.provider, key.key_value);
        }
        Ok(keys_map)
    }

    pub async fn get_api_key(&self, provider: &str) -> Result<Option<String>> {
        let repo = ApiKeyRepository::new(self.db);
        let api_key = repo.get_api_key_by_provider(provider).await?;
        Ok(api_key.map(|k| k.key_value))
    }
}
