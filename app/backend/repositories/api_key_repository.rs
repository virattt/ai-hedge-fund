use crate::database::models::ApiKey;
use anyhow::{Context, Result};
use sqlx::SqlitePool;

pub struct ApiKeyRepository<'a> {
    pub db: &'a SqlitePool,
}

impl<'a> ApiKeyRepository<'a> {
    pub fn new(db: &'a SqlitePool) -> Self {
        Self { db }
    }

    pub async fn create_or_update_api_key(
        &self,
        provider: &str,
        key_value: &str,
        description: Option<&str>,
        is_active: bool,
    ) -> Result<ApiKey> {
        let existing = sqlx::query_as::<_, ApiKey>("SELECT * FROM api_keys WHERE provider = $1")
            .bind(provider)
            .fetch_optional(self.db)
            .await?;

        if existing.is_some() {
            // Update
            sqlx::query_as::<_, ApiKey>(
                "UPDATE api_keys 
                 SET key_value = $1, description = $2, is_active = $3, updated_at = CURRENT_TIMESTAMP
                 WHERE provider = $4
                 RETURNING *"
            )
            .bind(key_value)
            .bind(description)
            .bind(is_active)
            .bind(provider)
            .fetch_one(self.db)
            .await
            .context("Failed to update API key")
        } else {
            // Insert
            sqlx::query_as::<_, ApiKey>(
                "INSERT INTO api_keys (provider, key_value, description, is_active)
                 VALUES ($1, $2, $3, $4)
                 RETURNING *",
            )
            .bind(provider)
            .bind(key_value)
            .bind(description)
            .bind(is_active)
            .fetch_one(self.db)
            .await
            .context("Failed to insert API key")
        }
    }

    pub async fn get_api_key_by_provider(&self, provider: &str) -> Result<Option<ApiKey>> {
        sqlx::query_as::<_, ApiKey>("SELECT * FROM api_keys WHERE provider = $1 AND is_active = 1")
            .bind(provider)
            .fetch_optional(self.db)
            .await
            .context("Failed to fetch API key")
    }

    pub async fn get_all_api_keys(&self, include_inactive: bool) -> Result<Vec<ApiKey>> {
        if include_inactive {
            sqlx::query_as::<_, ApiKey>("SELECT * FROM api_keys ORDER BY provider ASC")
                .fetch_all(self.db)
                .await
                .context("Failed to fetch all API keys")
        } else {
            sqlx::query_as::<_, ApiKey>(
                "SELECT * FROM api_keys WHERE is_active = 1 ORDER BY provider ASC",
            )
            .fetch_all(self.db)
            .await
            .context("Failed to fetch all active API keys")
        }
    }

    pub async fn update_api_key(
        &self,
        provider: &str,
        key_value: Option<&str>,
        description: Option<&str>,
        is_active: Option<bool>,
    ) -> Result<Option<ApiKey>> {
        let existing = sqlx::query_as::<_, ApiKey>("SELECT * FROM api_keys WHERE provider = $1")
            .bind(provider)
            .fetch_optional(self.db)
            .await?;

        let key = match existing {
            Some(k) => k,
            None => return Ok(None),
        };

        let binding_key = key.key_value.clone();
        let final_val = key_value.unwrap_or(&binding_key);
        let binding_desc = key.description.clone();
        let final_desc = description.or(binding_desc.as_deref());
        let final_active = is_active.unwrap_or(key.is_active);

        let updated = sqlx::query_as::<_, ApiKey>(
            "UPDATE api_keys 
             SET key_value = $1, description = $2, is_active = $3, updated_at = CURRENT_TIMESTAMP
             WHERE provider = $4
             RETURNING *",
        )
        .bind(final_val)
        .bind(final_desc)
        .bind(final_active)
        .bind(provider)
        .fetch_optional(self.db)
        .await
        .context("Failed to update API key fields")?;

        Ok(updated)
    }

    pub async fn delete_api_key(&self, provider: &str) -> Result<bool> {
        let res = sqlx::query("DELETE FROM api_keys WHERE provider = $1")
            .bind(provider)
            .execute(self.db)
            .await
            .context("Failed to delete API key")?;

        Ok(res.rows_affected() > 0)
    }

    pub async fn deactivate_api_key(&self, provider: &str) -> Result<bool> {
        let res = sqlx::query(
            "UPDATE api_keys SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE provider = $1",
        )
        .bind(provider)
        .execute(self.db)
        .await
        .context("Failed to deactivate API key")?;

        Ok(res.rows_affected() > 0)
    }

    pub async fn update_last_used(&self, provider: &str) -> Result<bool> {
        let res = sqlx::query(
            "UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE provider = $1 AND is_active = 1"
        )
        .bind(provider)
        .execute(self.db)
        .await
        .context("Failed to update last used timestamp")?;

        Ok(res.rows_affected() > 0)
    }

    pub async fn bulk_create_or_update(
        &self,
        api_keys_data: &[serde_json::Value],
    ) -> Result<Vec<ApiKey>> {
        let mut results = Vec::new();
        for item in api_keys_data {
            let provider = item
                .get("provider")
                .and_then(|v| v.as_str())
                .unwrap_or_default();
            let key_value = item
                .get("key_value")
                .and_then(|v| v.as_str())
                .unwrap_or_default();
            let description = item.get("description").and_then(|v| v.as_str());
            let is_active = item
                .get("is_active")
                .and_then(|v| v.as_bool())
                .unwrap_or(true);

            let key = self
                .create_or_update_api_key(provider, key_value, description, is_active)
                .await?;
            results.push(key);
        }
        Ok(results)
    }
}
