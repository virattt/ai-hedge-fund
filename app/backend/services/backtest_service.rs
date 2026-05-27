use crate::models::schemas::{BacktestDayResult, BacktestPerformanceMetrics, BacktestRequest};
use ai_hedge_fund::backtesting::controller::{AgentController, AgentRunRequest};
use ai_hedge_fund::backtesting::metrics::PerformanceMetricsCalculator;
use ai_hedge_fund::backtesting::portfolio::Portfolio;
use ai_hedge_fund::backtesting::trader::TradeExecutor;
use ai_hedge_fund::backtesting::types::{PerformanceMetrics, PortfolioValuePoint};
use ai_hedge_fund::cli::input::resolve_data_provider;
use ai_hedge_fund::data::provider::configure_provider;
use ai_hedge_fund::tools::api::get_prices;
use ai_hedge_fund::utils::llm::{log_resolved_llm_config, resolve_llm_config};
use anyhow::Result;
use chrono::{Datelike, NaiveDate};
use std::collections::HashMap;
use tokio::sync::mpsc;

pub struct BacktestService;

impl BacktestService {
    pub async fn run_backtest_streaming(
        req: BacktestRequest,
        tx: mpsc::Sender<Result<serde_json::Value>>,
    ) -> Result<()> {
        let tickers = req.base.tickers.clone();
        let start_date = req.start_date.clone();
        let end_date = req.end_date.clone();
        let initial_capital = req.initial_capital;
        let llm = resolve_llm_config(
            req.base.model_name.as_deref(),
            false,
            req.base.model_provider.clone(),
        );
        log_resolved_llm_config(&llm);
        let model_name = llm.model_name;
        let model_provider = llm.model_provider;

        let start_dt = NaiveDate::parse_from_str(&start_date, "%Y-%m-%d")?;
        let end_dt = NaiveDate::parse_from_str(&end_date, "%Y-%m-%d")?;

        let mut portfolio = Portfolio::new(
            tickers.clone(),
            initial_capital,
            req.base.margin_requirement,
        );
        let executor = TradeExecutor::new();
        let calculator = PerformanceMetricsCalculator::new();
        let controller = AgentController::new();

        let mut portfolio_values = Vec::new();
        let mut current_dt = start_dt;

        let mut selected_analysts = Vec::new();
        if let Some(ref configs) = req.base.agent_models {
            for config in configs {
                let base_key = crate::services::graph::extract_base_agent_key(&config.agent_id);
                selected_analysts.push(base_key);
            }
        }

        let api_key = std::env::var("FINANCIAL_DATASETS_API_KEY").ok();
        let data_provider = resolve_data_provider(None);
        configure_provider(Some(data_provider));

        while current_dt <= end_dt {
            let weekday = current_dt.weekday().number_from_monday();
            if weekday > 5 {
                current_dt = current_dt.succ_opt().unwrap();
                continue;
            }

            let current_date_str = current_dt.format("%Y-%m-%d").to_string();
            let previous_dt = current_dt - chrono::Duration::days(1);
            let previous_date_str = previous_dt.format("%Y-%m-%d").to_string();
            let mut daily_prices = HashMap::new();
            let mut missing_price = false;
            for ticker in &tickers {
                match get_prices(
                    ticker,
                    &previous_date_str,
                    &current_date_str,
                    api_key.as_deref(),
                )
                .await
                {
                    Ok(prices) => {
                        if let Some(p) = prices.last() {
                            daily_prices.insert(ticker.clone(), p.close);
                        } else {
                            missing_price = true;
                        }
                    }
                    Err(_) => {
                        missing_price = true;
                    }
                }
            }

            if missing_price {
                current_dt = current_dt.succ_opt().unwrap();
                continue;
            }

            // Invoke agent controller
            let provider_str = model_provider.value();
            let agent_output = match controller
                .run_agent(AgentRunRequest {
                    tickers: tickers.clone(),
                    end_date: &current_date_str,
                    portfolio: &portfolio,
                    model_name: &model_name,
                    model_provider: provider_str,
                    selected_analysts: selected_analysts.clone(),
                    data_provider: Some(data_provider),
                })
                .await
            {
                Ok(out) => out,
                Err(e) => {
                    tx.send(Err(anyhow::anyhow!("Error running agents: {}", e)))
                        .await
                        .ok();
                    return Ok(());
                }
            };

            let decisions_json = agent_output
                .decisions
                .clone()
                .unwrap_or_else(|| serde_json::json!({}));
            let decisions: HashMap<
                String,
                ai_hedge_fund::agents::portfolio_manager::PortfolioDecision,
            > = serde_json::from_value(decisions_json.clone()).unwrap_or_default();

            let mut executed_trades = HashMap::new();
            for ticker in &tickers {
                let mut executed_qty = 0;
                if let Some(dec) = decisions.get(ticker) {
                    if dec.action != "hold" && dec.quantity > 0 {
                        let price = *daily_prices.get(ticker).unwrap();
                        executed_qty = executor.execute_trade(
                            ticker,
                            &dec.action,
                            dec.quantity,
                            price,
                            &mut portfolio,
                        );
                    }
                }
                executed_trades.insert(ticker.clone(), executed_qty as i32);
            }

            let total_value = ai_hedge_fund::backtesting::valuation::calculate_portfolio_value(
                &portfolio,
                &daily_prices,
            );
            let exposures =
                ai_hedge_fund::backtesting::valuation::compute_exposures(&portfolio, &daily_prices);

            let point = PortfolioValuePoint {
                date: current_dt,
                portfolio_value: total_value,
                long_exposure: exposures.long_exposure,
                short_exposure: exposures.short_exposure,
                gross_exposure: exposures.gross_exposure,
                net_exposure: exposures.net_exposure,
                long_short_ratio: exposures.long_short_ratio,
            };
            portfolio_values.push(point.clone());

            // Build BacktestDayResult response
            let decisions_val: HashMap<String, serde_json::Value> =
                serde_json::from_value(decisions_json.clone()).unwrap_or_default();
            let signals_val = agent_output.analyst_signals.clone();

            let day_result = BacktestDayResult {
                date: current_date_str.clone(),
                portfolio_value: total_value,
                cash: portfolio.cash,
                decisions: decisions_val,
                executed_trades,
                analyst_signals: signals_val,
                current_prices: daily_prices,
                long_exposure: exposures.long_exposure,
                short_exposure: exposures.short_exposure,
                gross_exposure: exposures.gross_exposure,
                net_exposure: exposures.net_exposure,
                long_short_ratio: Some(exposures.long_short_ratio),
            };

            // Stream backtest result event
            let event = serde_json::json!({
                "type": "backtest_result",
                "data": day_result
            });
            tx.send(Ok(event)).await.ok();

            current_dt = current_dt.succ_opt().unwrap();
        }

        // Final completion event
        let mut final_metrics = PerformanceMetrics::default();
        if portfolio_values.len() > 1 {
            if let Some(comp) = calculator.compute_metrics(&portfolio_values) {
                final_metrics = comp;
            }
        }

        let metrics_resp = BacktestPerformanceMetrics {
            sharpe_ratio: Some(final_metrics.sharpe_ratio),
            sortino_ratio: final_metrics.sortino_ratio,
            max_drawdown: final_metrics.max_drawdown,
            max_drawdown_date: final_metrics.max_drawdown_date.clone(),
            long_short_ratio: final_metrics.long_short_ratio,
            gross_exposure: final_metrics.gross_exposure,
            net_exposure: final_metrics.net_exposure,
        };

        let completion_data = serde_json::json!({
            "type": "complete",
            "performance_metrics": metrics_resp,
            "final_portfolio": portfolio,
            "total_days": portfolio_values.len()
        });
        tx.send(Ok(completion_data)).await.ok();

        Ok(())
    }
}
