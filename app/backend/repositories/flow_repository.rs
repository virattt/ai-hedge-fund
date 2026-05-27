use crate::database::models::HedgeFundFlow;
use anyhow::{Context, Result};
use serde_json::Value;
use sqlx::SqlitePool;

pub struct FlowRepository<'a> {
    pub db: &'a SqlitePool,
}

pub struct FlowCreateInput<'a> {
    pub name: &'a str,
    pub nodes: &'a Value,
    pub edges: &'a Value,
    pub description: Option<&'a str>,
    pub viewport: Option<&'a Value>,
    pub data: Option<&'a Value>,
    pub is_template: bool,
    pub tags: Option<&'a Value>,
}

pub struct FlowUpdateInput<'a> {
    pub flow_id: i32,
    pub name: Option<&'a str>,
    pub description: Option<&'a str>,
    pub nodes: Option<&'a Value>,
    pub edges: Option<&'a Value>,
    pub viewport: Option<&'a Value>,
    pub data: Option<&'a Value>,
    pub is_template: Option<bool>,
    pub tags: Option<&'a Value>,
}

impl<'a> FlowRepository<'a> {
    pub fn new(db: &'a SqlitePool) -> Self {
        Self { db }
    }

    pub async fn create_flow(&self, input: FlowCreateInput<'_>) -> Result<HedgeFundFlow> {
        sqlx::query_as::<_, HedgeFundFlow>(
            "INSERT INTO hedge_fund_flows (name, description, nodes, edges, viewport, data, is_template, tags)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
             RETURNING *",
        )
        .bind(input.name)
        .bind(input.description)
        .bind(input.nodes)
        .bind(input.edges)
        .bind(input.viewport)
        .bind(input.data)
        .bind(input.is_template)
        .bind(input.tags)
        .fetch_one(self.db)
        .await
        .context("Failed to create flow")
    }

    pub async fn get_flow_by_id(&self, flow_id: i32) -> Result<Option<HedgeFundFlow>> {
        sqlx::query_as::<_, HedgeFundFlow>("SELECT * FROM hedge_fund_flows WHERE id = $1")
            .bind(flow_id)
            .fetch_optional(self.db)
            .await
            .context("Failed to get flow by ID")
    }

    pub async fn get_all_flows(&self, include_templates: bool) -> Result<Vec<HedgeFundFlow>> {
        if include_templates {
            sqlx::query_as::<_, HedgeFundFlow>(
                "SELECT * FROM hedge_fund_flows ORDER BY updated_at DESC",
            )
            .fetch_all(self.db)
            .await
            .context("Failed to get all flows")
        } else {
            sqlx::query_as::<_, HedgeFundFlow>(
                "SELECT * FROM hedge_fund_flows WHERE is_template = 0 ORDER BY updated_at DESC",
            )
            .fetch_all(self.db)
            .await
            .context("Failed to get all non-template flows")
        }
    }

    pub async fn get_flows_by_name(&self, name: &str) -> Result<Vec<HedgeFundFlow>> {
        let pattern = format!("%{name}%");
        sqlx::query_as::<_, HedgeFundFlow>(
            "SELECT * FROM hedge_fund_flows WHERE name LIKE $1 ORDER BY updated_at DESC",
        )
        .bind(pattern)
        .fetch_all(self.db)
        .await
        .context("Failed to get flows by name")
    }

    pub async fn update_flow(&self, input: FlowUpdateInput<'_>) -> Result<Option<HedgeFundFlow>> {
        let existing = self.get_flow_by_id(input.flow_id).await?;
        let flow = match existing {
            Some(f) => f,
            None => return Ok(None),
        };

        let binding_name = flow.name.clone();
        let final_name = input.name.unwrap_or(&binding_name);
        let binding_desc = flow.description.clone();
        let final_desc = input.description.or(binding_desc.as_deref());
        let final_nodes = input.nodes.unwrap_or(&flow.nodes);
        let final_edges = input.edges.unwrap_or(&flow.edges);
        let final_viewport = input.viewport.or(flow.viewport.as_ref());
        let final_data = input.data.or(flow.data.as_ref());
        let final_is_template = input.is_template.unwrap_or(flow.is_template);
        let final_tags = input.tags.or(flow.tags.as_ref());

        let updated = sqlx::query_as::<_, HedgeFundFlow>(
            "UPDATE hedge_fund_flows 
             SET name = $1, description = $2, nodes = $3, edges = $4, viewport = $5, data = $6, is_template = $7, tags = $8, updated_at = CURRENT_TIMESTAMP
             WHERE id = $9
             RETURNING *",
        )
        .bind(final_name)
        .bind(final_desc)
        .bind(final_nodes)
        .bind(final_edges)
        .bind(final_viewport)
        .bind(final_data)
        .bind(final_is_template)
        .bind(final_tags)
        .bind(input.flow_id)
        .fetch_optional(self.db)
        .await
        .context("Failed to update flow")?;

        Ok(updated)
    }

    pub async fn delete_flow(&self, flow_id: i32) -> Result<bool> {
        let res = sqlx::query("DELETE FROM hedge_fund_flows WHERE id = $1")
            .bind(flow_id)
            .execute(self.db)
            .await
            .context("Failed to delete flow")?;

        Ok(res.rows_affected() > 0)
    }

    pub async fn duplicate_flow(
        &self,
        flow_id: i32,
        new_name: Option<&str>,
    ) -> Result<Option<HedgeFundFlow>> {
        let original = match self.get_flow_by_id(flow_id).await? {
            Some(o) => o,
            None => return Ok(None),
        };

        let binding_copy_name = format!("{original_name} (Copy)", original_name = original.name);
        let copy_name = new_name.unwrap_or(&binding_copy_name);

        let copy = self
            .create_flow(FlowCreateInput {
                name: copy_name,
                nodes: &original.nodes,
                edges: &original.edges,
                description: original.description.as_deref(),
                viewport: original.viewport.as_ref(),
                data: original.data.as_ref(),
                is_template: false,
                tags: original.tags.as_ref(),
            })
            .await?;

        Ok(Some(copy))
    }
}
