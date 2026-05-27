use sqlx::SqlitePool;
use anyhow::{Result, Context};
use crate::database::models::HedgeFundFlowRun;

pub struct FlowRunRepository<'a> {
    pub db: &'a SqlitePool,
}

impl<'a> FlowRunRepository<'a> {
    pub fn new(db: &'a SqlitePool) -> Self {
        Self { db }
    }

    pub async fn create_flow_run(
        &self,
        flow_id: i32,
        request_data: Option<&serde_json::Value>,
    ) -> Result<HedgeFundFlowRun> {
        let run_number = self.get_next_run_number(flow_id).await?;

        sqlx::query_as::<_, HedgeFundFlowRun>(
            "INSERT INTO hedge_fund_flow_runs (flow_id, request_data, run_number, status)
             VALUES ($1, $2, $3, 'IDLE')
             RETURNING *"
        )
        .bind(flow_id)
        .bind(request_data)
        .bind(run_number)
        .fetch_one(self.db)
        .await
        .context("Failed to create flow run")
    }

    pub async fn get_flow_run_by_id(&self, run_id: i32) -> Result<Option<HedgeFundFlowRun>> {
        sqlx::query_as::<_, HedgeFundFlowRun>(
            "SELECT * FROM hedge_fund_flow_runs WHERE id = $1"
        )
        .bind(run_id)
        .fetch_optional(self.db)
        .await
        .context("Failed to get flow run by ID")
    }

    pub async fn get_flow_runs_by_flow_id(&self, flow_id: i32, limit: i32, offset: i32) -> Result<Vec<HedgeFundFlowRun>> {
        sqlx::query_as::<_, HedgeFundFlowRun>(
            "SELECT * FROM hedge_fund_flow_runs WHERE flow_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3"
        )
        .bind(flow_id)
        .bind(limit)
        .bind(offset)
        .fetch_all(self.db)
        .await
        .context("Failed to get flow runs by flow ID")
    }

    pub async fn get_active_flow_run(&self, flow_id: i32) -> Result<Option<HedgeFundFlowRun>> {
        sqlx::query_as::<_, HedgeFundFlowRun>(
            "SELECT * FROM hedge_fund_flow_runs WHERE flow_id = $1 AND status = 'IN_PROGRESS'"
        )
        .bind(flow_id)
        .fetch_optional(self.db)
        .await
        .context("Failed to get active flow run")
    }

    pub async fn get_latest_flow_run(&self, flow_id: i32) -> Result<Option<HedgeFundFlowRun>> {
        sqlx::query_as::<_, HedgeFundFlowRun>(
            "SELECT * FROM hedge_fund_flow_runs WHERE flow_id = $1 ORDER BY created_at DESC LIMIT 1"
        )
        .bind(flow_id)
        .fetch_optional(self.db)
        .await
        .context("Failed to get latest flow run")
    }

    pub async fn update_flow_run(
        &self,
        run_id: i32,
        status: Option<&str>,
        results: Option<&serde_json::Value>,
        error_message: Option<&str>,
    ) -> Result<Option<HedgeFundFlowRun>> {
        let existing = self.get_flow_run_by_id(run_id).await?;
        let flow_run = match existing {
            Some(r) => r,
            None => return Ok(None),
        };

        let binding_status = flow_run.status.clone();
        let final_status = status.unwrap_or(&binding_status);
        let final_results = results.or(flow_run.results.as_ref());
        let binding_error = flow_run.error_message.clone();
        let final_error = error_message.or(binding_error.as_deref());

        let mut started_at = flow_run.started_at;
        let mut completed_at = flow_run.completed_at;

        if let Some(s) = status {
            if s == "IN_PROGRESS" && started_at.is_none() {
                started_at = Some(chrono::Utc::now());
            } else if (s == "COMPLETE" || s == "ERROR") && completed_at.is_none() {
                completed_at = Some(chrono::Utc::now());
            }
        }

        let updated = sqlx::query_as::<_, HedgeFundFlowRun>(
            "UPDATE hedge_fund_flow_runs 
             SET status = $1, results = $2, error_message = $3, started_at = $4, completed_at = $5, updated_at = CURRENT_TIMESTAMP
             WHERE id = $6
             RETURNING *"
        )
        .bind(final_status)
        .bind(final_results)
        .bind(final_error)
        .bind(started_at)
        .bind(completed_at)
        .bind(run_id)
        .fetch_optional(self.db)
        .await
        .context("Failed to update flow run")?;

        Ok(updated)
    }

    pub async fn delete_flow_run(&self, run_id: i32) -> Result<bool> {
        let res = sqlx::query(
            "DELETE FROM hedge_fund_flow_runs WHERE id = $1"
        )
        .bind(run_id)
        .execute(self.db)
        .await
        .context("Failed to delete flow run")?;

        Ok(res.rows_affected() > 0)
    }

    pub async fn delete_flow_runs_by_flow_id(&self, flow_id: i32) -> Result<u64> {
        let res = sqlx::query(
            "DELETE FROM hedge_fund_flow_runs WHERE flow_id = $1"
        )
        .bind(flow_id)
        .execute(self.db)
        .await
        .context("Failed to delete flow runs by flow ID")?;

        Ok(res.rows_affected())
    }

    pub async fn get_flow_run_count(&self, flow_id: i32) -> Result<i64> {
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM hedge_fund_flow_runs WHERE flow_id = $1"
        )
        .bind(flow_id)
        .fetch_one(self.db)
        .await
        .context("Failed to get flow run count")?;

        Ok(count.0)
    }

    pub async fn get_next_run_number(&self, flow_id: i32) -> Result<i32> {
        let max_val: (Option<i32>,) = sqlx::query_as(
            "SELECT MAX(run_number) FROM hedge_fund_flow_runs WHERE flow_id = $1"
        )
        .bind(flow_id)
        .fetch_one(self.db)
        .await
        .context("Failed to query max run number")?;

        Ok(max_val.0.unwrap_or(0) + 1)
    }
}
