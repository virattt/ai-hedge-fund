use sqlx::SqlitePool;
use anyhow::{Result, Context};
use crate::database::models::HedgeFundFlow;

pub struct FlowRepository<'a> {
    pub db: &'a SqlitePool,
}

impl<'a> FlowRepository<'a> {
    pub fn new(db: &'a SqlitePool) -> Self {
        Self { db }
    }

    pub async fn create_flow(
        &self,
        name: &str,
        nodes: &serde_json::Value,
        edges: &serde_json::Value,
        description: Option<&str>,
        viewport: Option<&serde_json::Value>,
        data: Option<&serde_json::Value>,
        is_template: bool,
        tags: Option<&serde_json::Value>,
    ) -> Result<HedgeFundFlow> {
        sqlx::query_as::<_, HedgeFundFlow>(
            "INSERT INTO hedge_fund_flows (name, description, nodes, edges, viewport, data, is_template, tags)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
             RETURNING *"
        )
        .bind(name)
        .bind(description)
        .bind(nodes)
        .bind(edges)
        .bind(viewport)
        .bind(data)
        .bind(is_template)
        .bind(tags)
        .fetch_one(self.db)
        .await
        .context("Failed to create flow")
    }

    pub async fn get_flow_by_id(&self, flow_id: i32) -> Result<Option<HedgeFundFlow>> {
        sqlx::query_as::<_, HedgeFundFlow>(
            "SELECT * FROM hedge_fund_flows WHERE id = $1"
        )
        .bind(flow_id)
        .fetch_optional(self.db)
        .await
        .context("Failed to get flow by ID")
    }

    pub async fn get_all_flows(&self, include_templates: bool) -> Result<Vec<HedgeFundFlow>> {
        if include_templates {
            sqlx::query_as::<_, HedgeFundFlow>(
                "SELECT * FROM hedge_fund_flows ORDER BY updated_at DESC"
            )
            .fetch_all(self.db)
            .await
            .context("Failed to get all flows")
        } else {
            sqlx::query_as::<_, HedgeFundFlow>(
                "SELECT * FROM hedge_fund_flows WHERE is_template = 0 ORDER BY updated_at DESC"
            )
            .fetch_all(self.db)
            .await
            .context("Failed to get all non-template flows")
        }
    }

    pub async fn get_flows_by_name(&self, name: &str) -> Result<Vec<HedgeFundFlow>> {
        let pattern = format!("%{}%", name);
        sqlx::query_as::<_, HedgeFundFlow>(
            "SELECT * FROM hedge_fund_flows WHERE name LIKE $1 ORDER BY updated_at DESC"
        )
        .bind(pattern)
        .fetch_all(self.db)
        .await
        .context("Failed to get flows by name")
    }

    pub async fn update_flow(
        &self,
        flow_id: i32,
        name: Option<&str>,
        description: Option<&str>,
        nodes: Option<&serde_json::Value>,
        edges: Option<&serde_json::Value>,
        viewport: Option<&serde_json::Value>,
        data: Option<&serde_json::Value>,
        is_template: Option<bool>,
        tags: Option<&serde_json::Value>,
    ) -> Result<Option<HedgeFundFlow>> {
        let existing = self.get_flow_by_id(flow_id).await?;
        let flow = match existing {
            Some(f) => f,
            None => return Ok(None),
        };

        let binding_name = flow.name.clone();
        let final_name = name.unwrap_or(&binding_name);
        let binding_desc = flow.description.clone();
        let final_desc = description.or(binding_desc.as_deref());
        let final_nodes = nodes.unwrap_or(&flow.nodes);
        let final_edges = edges.unwrap_or(&flow.edges);
        let final_viewport = viewport.or(flow.viewport.as_ref());
        let final_data = data.or(flow.data.as_ref());
        let final_is_template = is_template.unwrap_or(flow.is_template);
        let final_tags = tags.or(flow.tags.as_ref());

        let updated = sqlx::query_as::<_, HedgeFundFlow>(
            "UPDATE hedge_fund_flows 
             SET name = $1, description = $2, nodes = $3, edges = $4, viewport = $5, data = $6, is_template = $7, tags = $8, updated_at = CURRENT_TIMESTAMP
             WHERE id = $9
             RETURNING *"
        )
        .bind(final_name)
        .bind(final_desc)
        .bind(final_nodes)
        .bind(final_edges)
        .bind(final_viewport)
        .bind(final_data)
        .bind(final_is_template)
        .bind(final_tags)
        .bind(flow_id)
        .fetch_optional(self.db)
        .await
        .context("Failed to update flow")?;

        Ok(updated)
    }

    pub async fn delete_flow(&self, flow_id: i32) -> Result<bool> {
        let res = sqlx::query(
            "DELETE FROM hedge_fund_flows WHERE id = $1"
        )
        .bind(flow_id)
        .execute(self.db)
        .await
        .context("Failed to delete flow")?;

        Ok(res.rows_affected() > 0)
    }

    pub async fn duplicate_flow(&self, flow_id: i32, new_name: Option<&str>) -> Result<Option<HedgeFundFlow>> {
        let original = match self.get_flow_by_id(flow_id).await? {
            Some(o) => o,
            None => return Ok(None),
        };

        let binding_copy_name = format!("{} (Copy)", original.name);
        let copy_name = new_name.unwrap_or(&binding_copy_name);

        let copy = self.create_flow(
            copy_name,
            &original.nodes,
            &original.edges,
            original.description.as_deref(),
            original.viewport.as_ref(),
            original.data.as_ref(),
            false,
            original.tags.as_ref(),
        )
        .await?;

        Ok(Some(copy))
    }
}
