use ai_hedge_fund::backtesting::portfolio::{Portfolio, PositionDetail};
use crate::models::schemas::PortfolioPosition;

pub fn create_portfolio(
    initial_cash: f64,
    margin_requirement: f64,
    tickers: &[String],
    portfolio_positions: Option<&[PortfolioPosition]>,
) -> Portfolio {
    let mut portfolio = Portfolio::new(tickers.to_vec(), initial_cash, margin_requirement);

    if let Some(positions) = portfolio_positions {
        for pos in positions {
            let ticker = &pos.ticker;
            let quantity = pos.quantity;
            let trade_price = pos.trade_price;

            if let Some(detail) = portfolio.positions.get_mut(ticker) {
                if quantity > 0.0 {
                    detail.long = quantity as i64;
                    detail.long_cost_basis = trade_price;
                } else if quantity < 0.0 {
                    detail.short = quantity.abs() as i64;
                    detail.short_cost_basis = trade_price;
                    detail.short_margin_used = quantity.abs() * trade_price * margin_requirement;
                    portfolio.margin_used += detail.short_margin_used;
                }
            }
        }
    }

    portfolio
}
