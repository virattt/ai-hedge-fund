//! Yahoo Finance fallbacks for endpoints unavailable on the free provider.

use anyhow::{Context, Result};
use chrono::NaiveDate;
use yfinance::{
    earnings::Earnings,
    fundamentals::{Fundamentals, FundamentalsKind},
    holders::InsiderTransaction,
    news::NewsTab,
    Ticker, YfClient,
};

use crate::data::models::{CompanyNews, FinancialMetrics, InsiderTrade, LineItem};
use crate::utils::financial_data::{
    calculate_gross_margin, calculate_net_margin, calculate_shareholders_equity,
    calculate_working_capital,
};

/// Fetch basic financial metrics from Yahoo quote summary / key statistics.
pub async fn get_financial_metrics_fallback(
    ticker: &str,
    end_date: &str,
    period: &str,
    limit: u32,
) -> Result<Vec<FinancialMetrics>> {
    let client = YfClient::new().context("Failed to create Yahoo Finance client")?;
    let ticker_obj = Ticker::new(&client, ticker);
    let info = ticker_obj.info().await?;

    let quarterly = period == "quarterly" || period == "ttm";
    let effective_limit = effective_fundamentals_limit(limit, quarterly);
    let income =
        fetch_fundamentals(&ticker_obj, FundamentalsKind::IncomeStatement, quarterly).await;
    let balance = fetch_fundamentals(&ticker_obj, FundamentalsKind::BalanceSheet, quarterly).await;
    let cashflow = fetch_fundamentals(&ticker_obj, FundamentalsKind::CashFlow, quarterly).await;

    let cutoff = NaiveDate::parse_from_str(end_date, "%Y-%m-%d").ok();
    let mut dates: Vec<NaiveDate> = income.as_ref().map(|f| f.dates()).unwrap_or_default();
    if dates.is_empty() {
        dates = balance.as_ref().map(|f| f.dates()).unwrap_or_default();
    }
    if let Some(cutoff_date) = cutoff {
        dates.retain(|d| *d <= cutoff_date);
    }
    dates.sort();
    dates.reverse();
    dates.truncate(effective_limit as usize);

    if dates.is_empty() {
        dates.push(cutoff.unwrap_or_else(|| chrono::Local::now().date_naive()));
    }

    let earnings = if quarterly {
        ticker_obj.earnings().await.ok()
    } else {
        None
    };

    let mut metrics: Vec<FinancialMetrics> = dates
        .into_iter()
        .map(|date| {
            let revenue = metric_value(&income, "TotalRevenue", date);
            let net_income = metric_value(&income, "NetIncome", date);
            let gross_profit = metric_value(&income, "GrossProfit", date);
            let operating_income = metric_value(&income, "OperatingIncome", date);
            let total_assets = metric_value(&balance, "TotalAssets", date);
            let total_liabilities =
                metric_value(&balance, "TotalLiabilitiesNetMinorityInterest", date);
            let shareholders_equity = metric_value(&balance, "StockholdersEquity", date)
                .or_else(|| calculate_shareholders_equity(total_assets, total_liabilities));
            let current_assets = metric_value(&balance, "CurrentAssets", date);
            let current_liabilities = metric_value(&balance, "CurrentLiabilities", date);
            let outstanding_shares = metric_value(&balance, "OrdinarySharesNumber", date);
            let free_cash_flow = metric_value(&cashflow, "FreeCashFlow", date);
            let eps = metric_value(&income, "BasicEPS", date)
                .or_else(|| metric_value(&income, "DilutedEPS", date))
                .or_else(|| safe_ratio(net_income, outstanding_shares));

            FinancialMetrics {
                ticker: ticker.to_string(),
                report_period: date.format("%Y-%m-%d").to_string(),
                period: period.to_string(),
                currency: info.currency.clone().unwrap_or_else(|| "USD".to_string()),
                market_cap: info.market_cap.map(|v| v as f64),
                enterprise_value: None,
                price_to_earnings_ratio: info.trailing_pe,
                price_to_book_ratio: raw_module_f64(
                    &info.raw,
                    "defaultKeyStatistics",
                    "priceToBook",
                ),
                price_to_sales_ratio: raw_module_f64(
                    &info.raw,
                    "summaryDetail",
                    "priceToSalesTrailing12Months",
                ),
                enterprise_value_to_ebitda_ratio: None,
                enterprise_value_to_revenue_ratio: None,
                free_cash_flow_yield: safe_ratio(free_cash_flow, info.market_cap.map(|v| v as f64)),
                peg_ratio: raw_module_f64(&info.raw, "defaultKeyStatistics", "pegRatio"),
                gross_margin: calculate_gross_margin(revenue, gross_profit),
                operating_margin: safe_ratio(operating_income, revenue),
                net_margin: calculate_net_margin(revenue, net_income),
                return_on_equity: safe_ratio(net_income, shareholders_equity),
                return_on_assets: safe_ratio(net_income, total_assets),
                return_on_invested_capital: None,
                asset_turnover: None,
                inventory_turnover: None,
                receivables_turnover: None,
                days_sales_outstanding: None,
                operating_cycle: None,
                working_capital_turnover: None,
                current_ratio: safe_ratio(current_assets, current_liabilities),
                quick_ratio: None,
                cash_ratio: None,
                operating_cash_flow_ratio: None,
                debt_to_equity: safe_ratio(
                    metric_value(&balance, "TotalDebt", date),
                    shareholders_equity,
                ),
                debt_to_assets: safe_ratio(metric_value(&balance, "TotalDebt", date), total_assets),
                interest_coverage: None,
                revenue_growth: None,
                earnings_growth: None,
                book_value_growth: None,
                earnings_per_share_growth: None,
                free_cash_flow_growth: None,
                operating_income_growth: None,
                ebitda_growth: None,
                payout_ratio: None,
                earnings_per_share: eps.or(info.trailing_eps),
                book_value_per_share: raw_module_f64(
                    &info.raw,
                    "defaultKeyStatistics",
                    "bookValue",
                ),
                free_cash_flow_per_share: None,
                revenue,
                beta: info.beta,
                operating_income,
                free_cash_flow,
                ev_to_ebit: None,
            }
        })
        .collect();

    if let Some(ref earn) = earnings {
        supplement_metrics_from_earnings(&mut metrics, earn);
    }

    enrich_derived_growth(&mut metrics);

    Ok(metrics)
}

/// Build line items from Yahoo fundamentals timeseries for requested fields.
pub async fn search_line_items_fallback(
    ticker: &str,
    line_items: Vec<String>,
    end_date: &str,
    period: &str,
    limit: u32,
) -> Result<Vec<LineItem>> {
    let client = YfClient::new().context("Failed to create Yahoo Finance client")?;
    let ticker_obj = Ticker::new(&client, ticker);
    let quarterly = period == "quarterly" || period == "ttm";

    let income =
        fetch_fundamentals(&ticker_obj, FundamentalsKind::IncomeStatement, quarterly).await;
    let balance = fetch_fundamentals(&ticker_obj, FundamentalsKind::BalanceSheet, quarterly).await;
    let cashflow = fetch_fundamentals(&ticker_obj, FundamentalsKind::CashFlow, quarterly).await;

    let cutoff = NaiveDate::parse_from_str(end_date, "%Y-%m-%d").ok();
    let mut dates: Vec<NaiveDate> = income.as_ref().map(|f| f.dates()).unwrap_or_default();
    if dates.is_empty() {
        dates = balance.as_ref().map(|f| f.dates()).unwrap_or_default();
    }
    if let Some(cutoff_date) = cutoff {
        dates.retain(|d| *d <= cutoff_date);
    }
    dates.sort();
    dates.reverse();
    let effective_limit = effective_fundamentals_limit(limit, quarterly);
    dates.truncate(effective_limit as usize);

    if dates.is_empty() {
        return Ok(Vec::new());
    }

    let items: Vec<LineItem> = dates
        .into_iter()
        .map(|date| {
            let current_assets = metric_value(&balance, "CurrentAssets", date);
            let current_liabilities = metric_value(&balance, "CurrentLiabilities", date);
            let total_assets = metric_value(&balance, "TotalAssets", date);
            let total_liabilities =
                metric_value(&balance, "TotalLiabilitiesNetMinorityInterest", date);
            let revenue = metric_value(&income, "TotalRevenue", date);
            let gross_profit = metric_value(&income, "GrossProfit", date);
            let net_income = metric_value(&income, "NetIncome", date);
            let operating_income = metric_value(&income, "OperatingIncome", date);
            let ebit = metric_value(&income, "EBIT", date);
            let ebitda = metric_value(&income, "EBITDA", date);
            let shareholders_equity = metric_value(&balance, "StockholdersEquity", date)
                .or_else(|| calculate_shareholders_equity(total_assets, total_liabilities));
            let outstanding_shares = metric_value(&balance, "OrdinarySharesNumber", date);
            let working_capital = metric_value(&balance, "WorkingCapital", date)
                .or_else(|| calculate_working_capital(current_assets, current_liabilities));

            let mut item = LineItem {
                ticker: ticker.to_string(),
                report_period: date.format("%Y-%m-%d").to_string(),
                period: period.to_string(),
                currency: "USD".to_string(),
                capital_expenditure: metric_value(&cashflow, "CapitalExpenditure", date),
                depreciation_and_amortization: metric_value(
                    &cashflow,
                    "DepreciationAndAmortization",
                    date,
                ),
                net_income,
                outstanding_shares: outstanding_shares.map(|v| v as i64),
                total_assets,
                total_liabilities,
                shareholders_equity,
                dividends_and_other_cash_distributions: metric_value(
                    &cashflow,
                    "CashDividendsPaid",
                    date,
                ),
                issuance_or_purchase_of_equity_shares: metric_value(
                    &cashflow,
                    "NetCommonStockIssuance",
                    date,
                ),
                gross_profit,
                revenue,
                free_cash_flow: metric_value(&cashflow, "FreeCashFlow", date),
                working_capital,
                earnings_per_share: metric_value(&income, "BasicEPS", date)
                    .or_else(|| metric_value(&income, "DilutedEPS", date)),
                current_assets,
                current_liabilities,
                operating_margin: safe_ratio(operating_income, revenue),
                return_on_invested_capital: None,
                gross_margin: calculate_gross_margin(revenue, gross_profit),
                total_debt: metric_value(&balance, "TotalDebt", date),
                cash_and_equivalents: metric_value(&balance, "CashAndCashEquivalents", date),
                operating_income,
                ebit,
                ebitda,
                debt_to_equity: safe_ratio(
                    metric_value(&balance, "TotalDebt", date),
                    shareholders_equity,
                ),
                goodwill_and_intangible_assets: metric_value(
                    &balance,
                    "GoodwillAndOtherIntangibleAssets",
                    date,
                ),
                operating_expense: metric_value(&income, "OperatingExpense", date),
                research_and_development: metric_value(&income, "ResearchAndDevelopment", date),
                interest_expense: metric_value(&income, "InterestExpense", date),
                book_value_per_share: book_value_per_share(shareholders_equity, outstanding_shares),
            };

            // Only populate fields explicitly requested (others remain as computed above).
            if !line_items.is_empty() {
                filter_line_item_fields(&mut item, &line_items);
            }

            item
        })
        .collect();

    Ok(items)
}

/// Fetch insider transactions from Yahoo `holders()` (insiderTransactions module).
pub async fn get_insider_trades_fallback(
    ticker: &str,
    end_date: &str,
    start_date: Option<&str>,
    limit: u32,
) -> Result<Vec<InsiderTrade>> {
    let client = YfClient::new().context("Failed to create Yahoo Finance client")?;
    let ticker_obj = Ticker::new(&client, ticker);
    let holders = ticker_obj.holders().await?;

    let end_dt = NaiveDate::parse_from_str(end_date, "%Y-%m-%d").ok();
    let start_dt = start_date.and_then(|s| NaiveDate::parse_from_str(s, "%Y-%m-%d").ok());

    let mut trades: Vec<InsiderTrade> = holders
        .insider_transactions
        .into_iter()
        .filter_map(|tx| map_insider_transaction(ticker, &tx))
        .filter(|trade| insider_trade_in_range(trade, end_dt, start_dt))
        .collect();

    trades.sort_by(|a, b| b.filing_date.cmp(&a.filing_date));
    trades.truncate(limit as usize);

    Ok(trades)
}

/// Fetch company news headlines from Yahoo Finance with neutral sentiment.
pub async fn get_company_news_fallback(
    ticker: &str,
    end_date: &str,
    start_date: Option<&str>,
    limit: u32,
) -> Result<Vec<CompanyNews>> {
    let client = YfClient::new().context("Failed to create Yahoo Finance client")?;
    let ticker_obj = Ticker::new(&client, ticker);
    let articles = ticker_obj
        .news()
        .count(limit)
        .tab(NewsTab::LatestNews)
        .fetch()
        .await?;

    let end_dt = NaiveDate::parse_from_str(end_date, "%Y-%m-%d").ok();
    let start_dt = start_date.and_then(|s| NaiveDate::parse_from_str(s, "%Y-%m-%d").ok());

    let news: Vec<CompanyNews> = articles
        .into_iter()
        .filter_map(|article| {
            let date = article
                .published_at
                .and_then(|ts| chrono::DateTime::from_timestamp(ts, 0).map(|dt| dt.date_naive()))?;

            if let Some(end) = end_dt {
                if date > end {
                    return None;
                }
            }
            if let Some(start) = start_dt {
                if date < start {
                    return None;
                }
            }

            Some(CompanyNews {
                ticker: ticker.to_string(),
                title: article.title,
                author: None,
                source: article
                    .publisher
                    .unwrap_or_else(|| "Yahoo Finance".to_string()),
                date: date.format("%Y-%m-%d").to_string(),
                url: article.link.unwrap_or_default(),
                sentiment: Some("neutral".to_string()),
            })
        })
        .take(limit as usize)
        .collect();

    Ok(news)
}

/// Yahoo returns ~4–6 quarterly periods; request at least 8 when agents ask for depth.
fn effective_fundamentals_limit(limit: u32, quarterly: bool) -> u32 {
    if quarterly {
        limit.max(8)
    } else {
        limit
    }
}

/// Fill missing EPS/revenue on the newest rows from `earnings()` supplemental charts.
fn supplement_metrics_from_earnings(metrics: &mut [FinancialMetrics], earnings: &Earnings) {
    for (i, metric) in metrics.iter_mut().enumerate() {
        if metric.revenue.is_none() {
            if let Some(q) = earnings.quarterly.get(i) {
                metric.revenue = q.revenue;
            }
        }
        if metric.earnings_per_share.is_none() {
            if let Some(e) = earnings.eps_quarterly.get(i) {
                metric.earnings_per_share = e.actual;
            }
        }
    }
}

fn book_value_per_share(equity: Option<f64>, shares: Option<f64>) -> Option<f64> {
    safe_ratio(equity, shares)
}

fn map_insider_transaction(ticker: &str, tx: &InsiderTransaction) -> Option<InsiderTrade> {
    let filing_date = tx.start_date.clone().unwrap_or_else(|| {
        chrono::Local::now()
            .date_naive()
            .format("%Y-%m-%d")
            .to_string()
    });
    let transaction_date = tx.start_date.clone();
    let shares = signed_transaction_shares(tx.shares, tx.transaction.as_deref())?;
    let value = tx.value.map(|v| v as f64);

    Some(InsiderTrade {
        ticker: ticker.to_string(),
        issuer: None,
        name: Some(tx.name.clone()),
        title: tx.relation.clone(),
        is_board_director: None,
        transaction_date,
        transaction_shares: Some(shares),
        transaction_price_per_share: safe_ratio(value, Some(shares.abs())),
        transaction_value: value,
        shares_owned_before_transaction: None,
        shares_owned_after_transaction: None,
        security_title: tx.ownership.clone(),
        filing_date,
    })
}

/// Agents treat positive shares as buys and negative as sells.
pub fn signed_transaction_shares(shares: Option<u64>, transaction: Option<&str>) -> Option<f64> {
    let raw = shares? as f64;
    let tx = transaction.unwrap_or("").to_ascii_lowercase();
    if tx.contains("sale")
        || tx.contains("sell")
        || tx.contains("disposition")
        || tx.contains("disposed")
    {
        Some(-raw.abs())
    } else if tx.contains("purchase")
        || tx.contains("buy")
        || tx.contains("acquisition")
        || tx.contains("acquired")
    {
        Some(raw.abs())
    } else {
        // Grants, awards, and other filings default to positive (aligned with FD fixtures).
        Some(raw.abs())
    }
}

fn insider_trade_in_range(
    trade: &InsiderTrade,
    end: Option<NaiveDate>,
    start: Option<NaiveDate>,
) -> bool {
    let filing = parse_insider_date(&trade.filing_date);
    let tx_date = trade
        .transaction_date
        .as_ref()
        .and_then(|d| parse_insider_date(d));
    let date = tx_date.or(filing);
    let Some(date) = date else {
        return true;
    };
    if let Some(end) = end {
        if date > end {
            return false;
        }
    }
    if let Some(start) = start {
        if date < start {
            return false;
        }
    }
    true
}

fn parse_insider_date(s: &str) -> Option<NaiveDate> {
    let day = s.split('T').next().unwrap_or(s);
    NaiveDate::parse_from_str(day, "%Y-%m-%d").ok()
}

fn metric_value(fundamentals: &Option<Fundamentals>, metric: &str, date: NaiveDate) -> Option<f64> {
    fundamentals.as_ref()?.value(metric, date)
}

async fn fetch_fundamentals(
    ticker: &Ticker,
    kind: FundamentalsKind,
    quarterly: bool,
) -> Option<Fundamentals> {
    match kind {
        FundamentalsKind::IncomeStatement if quarterly => ticker.quarterly_income_stmt().await.ok(),
        FundamentalsKind::IncomeStatement => ticker.income_stmt().await.ok(),
        FundamentalsKind::BalanceSheet if quarterly => ticker.quarterly_balance_sheet().await.ok(),
        FundamentalsKind::BalanceSheet => ticker.balance_sheet().await.ok(),
        FundamentalsKind::CashFlow if quarterly => ticker.quarterly_cashflow().await.ok(),
        FundamentalsKind::CashFlow => ticker.cashflow().await.ok(),
    }
}

fn safe_ratio(numerator: Option<f64>, denominator: Option<f64>) -> Option<f64> {
    match (numerator, denominator) {
        (Some(n), Some(d)) if d.abs() > f64::EPSILON => Some(n / d),
        _ => None,
    }
}

/// Period-over-period or YoY growth rate: `(current - prior) / |prior|`.
pub fn compute_growth_rate(current: Option<f64>, prior: Option<f64>) -> Option<f64> {
    match (current, prior) {
        (Some(c), Some(p)) if p.abs() > f64::EPSILON => Some((c - p) / p.abs()),
        _ => None,
    }
}

/// Fill growth fields on metrics sorted newest-first. Prefers YoY (4 quarters back), else PoP.
pub fn enrich_derived_growth(metrics: &mut [FinancialMetrics]) {
    let n = metrics.len();
    for i in 0..n {
        let yoy_idx = i + 4;
        let pop_idx = i + 1;

        let prior_rev = if yoy_idx < n {
            metrics[yoy_idx].revenue
        } else {
            metrics.get(pop_idx).and_then(|m| m.revenue)
        };
        metrics[i].revenue_growth = compute_growth_rate(metrics[i].revenue, prior_rev);

        let prior_eps = if yoy_idx < n {
            metrics[yoy_idx].earnings_per_share
        } else {
            metrics.get(pop_idx).and_then(|m| m.earnings_per_share)
        };
        metrics[i].earnings_per_share_growth =
            compute_growth_rate(metrics[i].earnings_per_share, prior_eps);

        let prior_fcf = if yoy_idx < n {
            metrics[yoy_idx].free_cash_flow
        } else {
            metrics.get(pop_idx).and_then(|m| m.free_cash_flow)
        };
        metrics[i].free_cash_flow_growth =
            compute_growth_rate(metrics[i].free_cash_flow, prior_fcf);

        let prior_oi = if yoy_idx < n {
            metrics[yoy_idx].operating_income
        } else {
            metrics.get(pop_idx).and_then(|m| m.operating_income)
        };
        metrics[i].operating_income_growth =
            compute_growth_rate(metrics[i].operating_income, prior_oi);
    }
}

fn raw_module_f64(
    raw: &serde_json::Map<String, serde_json::Value>,
    module: &str,
    key: &str,
) -> Option<f64> {
    raw.get(module).and_then(|m| m.get(key)).and_then(|v| {
        if let Some(obj) = v.as_object() {
            obj.get("raw").and_then(|r| r.as_f64())
        } else {
            v.as_f64()
        }
    })
}

fn filter_line_item_fields(item: &mut LineItem, requested: &[String]) {
    let requested_set: std::collections::HashSet<&str> =
        requested.iter().map(|s| s.as_str()).collect();

    macro_rules! clear_unless {
        ($field:ident) => {
            if !requested_set.contains(stringify!($field)) {
                item.$field = None;
            }
        };
    }

    clear_unless!(capital_expenditure);
    clear_unless!(depreciation_and_amortization);
    clear_unless!(net_income);
    clear_unless!(outstanding_shares);
    clear_unless!(total_assets);
    clear_unless!(total_liabilities);
    clear_unless!(shareholders_equity);
    clear_unless!(dividends_and_other_cash_distributions);
    clear_unless!(issuance_or_purchase_of_equity_shares);
    clear_unless!(gross_profit);
    clear_unless!(revenue);
    clear_unless!(free_cash_flow);
    clear_unless!(working_capital);
    clear_unless!(earnings_per_share);
    clear_unless!(current_assets);
    clear_unless!(current_liabilities);
    clear_unless!(book_value_per_share);
    clear_unless!(operating_margin);
    clear_unless!(return_on_invested_capital);
    clear_unless!(gross_margin);
    clear_unless!(total_debt);
    clear_unless!(cash_and_equivalents);
    clear_unless!(operating_income);
    clear_unless!(ebit);
    clear_unless!(ebitda);
    clear_unless!(debt_to_equity);
    clear_unless!(goodwill_and_intangible_assets);
    clear_unless!(operating_expense);
    clear_unless!(research_and_development);
    clear_unless!(interest_expense);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::models::FinancialMetrics;

    fn sample_metric(revenue: Option<f64>, eps: Option<f64>, fcf: Option<f64>) -> FinancialMetrics {
        FinancialMetrics {
            ticker: "TEST".to_string(),
            report_period: "2024-01-01".to_string(),
            period: "ttm".to_string(),
            currency: "USD".to_string(),
            market_cap: None,
            enterprise_value: None,
            price_to_earnings_ratio: None,
            price_to_book_ratio: None,
            price_to_sales_ratio: None,
            enterprise_value_to_ebitda_ratio: None,
            enterprise_value_to_revenue_ratio: None,
            free_cash_flow_yield: None,
            peg_ratio: None,
            gross_margin: None,
            operating_margin: None,
            net_margin: None,
            return_on_equity: None,
            return_on_assets: None,
            return_on_invested_capital: None,
            asset_turnover: None,
            inventory_turnover: None,
            receivables_turnover: None,
            days_sales_outstanding: None,
            operating_cycle: None,
            working_capital_turnover: None,
            current_ratio: None,
            quick_ratio: None,
            cash_ratio: None,
            operating_cash_flow_ratio: None,
            debt_to_equity: None,
            debt_to_assets: None,
            interest_coverage: None,
            revenue_growth: None,
            earnings_growth: None,
            book_value_growth: None,
            earnings_per_share_growth: None,
            free_cash_flow_growth: None,
            operating_income_growth: None,
            ebitda_growth: None,
            payout_ratio: None,
            earnings_per_share: eps,
            book_value_per_share: None,
            free_cash_flow_per_share: None,
            revenue,
            beta: None,
            operating_income: None,
            free_cash_flow: fcf,
            ev_to_ebit: None,
        }
    }

    #[test]
    fn compute_growth_rate_handles_zero_prior() {
        assert_eq!(compute_growth_rate(Some(110.0), Some(100.0)), Some(0.1));
        assert_eq!(compute_growth_rate(Some(110.0), Some(0.0)), None);
        assert_eq!(compute_growth_rate(None, Some(100.0)), None);
    }

    #[test]
    fn enrich_derived_growth_populates_pop_when_two_quarters() {
        // newest first
        let mut metrics = vec![
            sample_metric(Some(110.0), Some(1.1), Some(55.0)),
            sample_metric(Some(100.0), Some(1.0), Some(50.0)),
        ];
        enrich_derived_growth(&mut metrics);
        assert!((metrics[0].revenue_growth.unwrap() - 0.1).abs() < 1e-9);
        assert!((metrics[0].earnings_per_share_growth.unwrap() - 0.1).abs() < 1e-9);
        assert!((metrics[0].free_cash_flow_growth.unwrap() - 0.1).abs() < 1e-9);
        assert!(metrics[1].revenue_growth.is_none());
    }

    #[test]
    fn enrich_derived_growth_prefers_yoy_with_five_quarters() {
        let mut metrics = vec![
            sample_metric(Some(200.0), Some(2.0), Some(100.0)),
            sample_metric(Some(180.0), Some(1.8), Some(90.0)),
            sample_metric(Some(160.0), Some(1.6), Some(80.0)),
            sample_metric(Some(140.0), Some(1.4), Some(70.0)),
            sample_metric(Some(100.0), Some(1.0), Some(50.0)),
        ];
        enrich_derived_growth(&mut metrics);
        assert_eq!(metrics[0].revenue_growth, Some(1.0));
    }

    #[test]
    fn signed_transaction_shares_marks_sales_negative() {
        assert_eq!(
            signed_transaction_shares(Some(1000), Some("Sale at price 150")),
            Some(-1000.0)
        );
        assert_eq!(
            signed_transaction_shares(Some(500), Some("Purchase of common stock")),
            Some(500.0)
        );
    }

    #[tokio::test]
    async fn line_items_fallback_does_not_panic_on_missing_data() {
        let items = search_line_items_fallback(
            "ZZZZINVALID",
            vec!["total_assets".to_string(), "working_capital".to_string()],
            "2024-01-01",
            "annual",
            1,
        )
        .await;
        assert!(items.is_ok());
    }
}
