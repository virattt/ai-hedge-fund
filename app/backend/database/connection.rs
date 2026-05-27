use sqlx::sqlite::{SqlitePool, SqlitePoolOptions};
use std::path::Path;
use anyhow::{Result, Context};

pub async fn get_db_pool() -> Result<SqlitePool> {
    // Determine database path dynamically (check both repository root and backend folder executions)
    let mut db_path = "app/backend/hedge_fund.db".to_string();
    if !Path::new(&db_path).exists() && (Path::new("hedge_fund.db").exists() || Path::new("../hedge_fund.db").exists()) {
        if Path::new("../hedge_fund.db").exists() {
            db_path = "../hedge_fund.db".to_string();
        } else {
            db_path = "hedge_fund.db".to_string();
        }
    }
    
    let db_url = format!("sqlite://{}", db_path);
    
    // Ensure parent directories exist
    if let Some(parent) = Path::new(&db_path).parent() {
        std::fs::create_dir_all(parent).ok();
    }
    
    let pool = SqlitePoolOptions::new()
        .max_connections(5)
        .connect(&db_url)
        .await
        .context("Failed to connect to SQLite database")?;
        
    // Auto-initialize tables
    init_db(&pool).await?;
        
    Ok(pool)
}

pub async fn init_db(pool: &SqlitePool) -> Result<()> {
    // 1. Create api_keys table
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            provider TEXT NOT NULL UNIQUE,
            key_value TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            description TEXT,
            last_used DATETIME
        )"
    )
    .execute(pool)
    .await?;

    // 2. Create hedge_fund_flows table
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS hedge_fund_flows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            name TEXT NOT NULL,
            description TEXT,
            nodes TEXT NOT NULL,
            edges TEXT NOT NULL,
            viewport TEXT,
            data TEXT,
            is_template BOOLEAN DEFAULT 0,
            tags TEXT
        )"
    )
    .execute(pool)
    .await?;

    // 3. Create hedge_fund_flow_runs table
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS hedge_fund_flow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'IDLE',
            started_at DATETIME,
            completed_at DATETIME,
            trading_mode TEXT NOT NULL DEFAULT 'one-time',
            schedule TEXT,
            duration TEXT,
            request_data TEXT,
            initial_portfolio TEXT,
            final_portfolio TEXT,
            results TEXT,
            error_message TEXT,
            run_number INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(flow_id) REFERENCES hedge_fund_flows(id)
        )"
    )
    .execute(pool)
    .await?;

    // 4. Create hedge_fund_flow_run_cycles table
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS hedge_fund_flow_run_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flow_run_id INTEGER NOT NULL,
            cycle_number INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            started_at DATETIME NOT NULL,
            completed_at DATETIME,
            analyst_signals TEXT,
            trading_decisions TEXT,
            executed_trades TEXT,
            portfolio_snapshot TEXT,
            performance_metrics TEXT,
            status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
            error_message TEXT,
            llm_calls_count INTEGER DEFAULT 0,
            api_calls_count INTEGER DEFAULT 0,
            estimated_cost TEXT,
            trigger_reason TEXT,
            market_conditions TEXT,
            FOREIGN KEY(flow_run_id) REFERENCES hedge_fund_flow_runs(id)
        )"
    )
    .execute(pool)
    .await?;

    Ok(())
}
