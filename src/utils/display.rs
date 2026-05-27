// Source: src/utils/display.py
//! Sibling to src/utils/display.py
//! Formats and displays pretty-printed CLI console logs of trading decisions, portfolio metrics, and agent recommendations.

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum BacktestRow {
    Summary {
        date: String,
        label: String,
        total_position_value: f64,
        cash_balance: f64,
        short_sale_proceeds: f64,
        margin_used: f64,
        available_cash: f64,
        total_value: f64,
        return_pct: f64,
        sharpe_ratio: Option<f64>,
        sortino_ratio: Option<f64>,
        max_drawdown: Option<f64>,
        benchmark_return_pct: Option<f64>,
    },
    Trade {
        date: String,
        ticker: String,
        action: String,
        quantity: f64,
        price: f64,
        long_shares: f64,
        short_shares: f64,
        position_value: f64,
    },
}

/// Print formatted trading results with colored tables for multiple tickers.
pub fn print_trading_output(result: &serde_json::Value) {
    let decisions = match result.get("decisions") {
        Some(d) => d,
        None => {
            println!("\x1b[31mNo trading decisions available\x1b[0m");
            return;
        }
    };

    let decisions_map = match decisions.as_object() {
        Some(m) => m,
        None => return,
    };

    for (ticker, decision) in decisions_map {
        println!("\n\x1b[1m\x1b[37mAnalysis for \x1b[36m{}\x1b[0m", ticker);
        println!("\x1b[1m\x1b[37m==================================================\x1b[0m");

        // Print trading decision table
        let action = decision
            .get("action")
            .and_then(|v| v.as_str())
            .unwrap_or("hold")
            .to_uppercase();
        let qty = decision
            .get("quantity")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let conf = decision
            .get("confidence")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let reasoning = decision
            .get("reasoning")
            .and_then(|v| v.as_str())
            .unwrap_or("");

        let action_color = match action.as_str() {
            "BUY" | "COVER" => "\x1b[32m",
            "SELL" | "SHORT" => "\x1b[31m",
            _ => "\x1b[33m",
        };

        println!(
            "\x1b[1m\x1b[37mTRADING DECISION:\x1b[0m [\x1b[36m{}\x1b[0m]",
            ticker
        );
        println!("+------------+----------------------------------------------------+");
        println!("| Action     | {}{:<50}\x1b[0m |", action_color, action);
        println!("| Quantity   | {}{:<50.0}\x1b[0m |", action_color, qty);
        println!("| Confidence | \x1b[37m{:<50.1}%\x1b[0m |", conf);

        // Wrap reasoning
        let words = reasoning.split_whitespace();
        let mut current_line = String::new();
        let mut first = true;

        for word in words {
            if current_line.len() + word.len() + 1 > 48 {
                if first {
                    println!("| Reasoning  | {:<50} |", current_line);
                    first = false;
                } else {
                    println!("|            | {:<50} |", current_line);
                }
                current_line = word.to_string();
            } else {
                if current_line.is_empty() {
                    current_line = word.to_string();
                } else {
                    current_line.push(' ');
                    current_line.push_str(word);
                }
            }
        }
        if !current_line.is_empty() {
            if first {
                println!("| Reasoning  | {:<50} |", current_line);
            } else {
                println!("|            | {:<50} |", current_line);
            }
        }
        println!("+------------+----------------------------------------------------+");
    }
}

/// Print the backtest results in a nicely formatted table
pub fn print_backtest_results(table_rows: &[BacktestRow]) {
    // Clear the screen
    print!("{}[2J{}[1;1H", 27 as char, 27 as char);

    // Find the latest summary row (we search for the summary with the max date)
    let latest_summary = table_rows
        .iter()
        .filter(|row| matches!(row, BacktestRow::Summary { .. }))
        .max_by_key(|row| match row {
            BacktestRow::Summary { date, .. } => date.clone(),
            _ => String::new(),
        });

    if let Some(BacktestRow::Summary {
        total_position_value,
        cash_balance,
        short_sale_proceeds,
        margin_used,
        available_cash,
        total_value,
        return_pct,
        sharpe_ratio,
        sortino_ratio,
        max_drawdown,
        benchmark_return_pct,
        ..
    }) = latest_summary
    {
        println!("\n\x1b[1m\x1b[37mPORTFOLIO SUMMARY:\x1b[0m");
        println!("Cash Balance: \x1b[36m${:.2}\x1b[0m", cash_balance);
        if *short_sale_proceeds > 0.0 || *margin_used > 0.0 {
            println!(
                "Short Sale Proceeds: \x1b[36m${:.2}\x1b[0m",
                short_sale_proceeds
            );
            println!("Margin Used: \x1b[36m${:.2}\x1b[0m", margin_used);
            println!("Available Cash: \x1b[36m${:.2}\x1b[0m", available_cash);
        }
        println!(
            "Net Position Value: \x1b[33m${:.2}\x1b[0m",
            total_position_value
        );
        println!("Total Value: \x1b[37m${:.2}\x1b[0m", total_value);

        let ret_color = if *return_pct >= 0.0 {
            "\x1b[32m"
        } else {
            "\x1b[31m"
        };
        println!("Portfolio Return: {}{:+0.2}%\x1b[0m", ret_color, return_pct);

        if let Some(bench) = benchmark_return_pct {
            let bench_color = if *bench >= 0.0 {
                "\x1b[32m"
            } else {
                "\x1b[31m"
            };
            println!("Benchmark Return: {}{:+0.2}%\x1b[0m", bench_color, bench);
        }

        if let Some(sharpe) = sharpe_ratio {
            println!("Sharpe Ratio: \x1b[33m{:.2}\x1b[0m", sharpe);
        }
        if let Some(sortino) = sortino_ratio {
            println!("Sortino Ratio: \x1b[33m{:.2}\x1b[0m", sortino);
        }
        if let Some(dd) = max_drawdown {
            println!("Max Drawdown: \x1b[31m{:.2}%\x1b[0m", dd);
        }
    }

    println!("\n");

    // Print header
    let header_border = "+------------+--------+--------+----------+----------+-------------+--------------+--------------------+";
    println!("{}", header_border);
    println!(
        "| {:<10} | {:<6} | {:^6} | {:>8} | {:>8} | {:>11} | {:>12} | {:>18} |",
        "Date",
        "Ticker",
        "Action",
        "Quantity",
        "Price",
        "Long Shares",
        "Short Shares",
        "Net Position Value"
    );
    println!("{}", header_border);

    // Print trade rows
    for row in table_rows {
        if let BacktestRow::Trade {
            date,
            ticker,
            action,
            quantity,
            price,
            long_shares,
            short_shares,
            position_value,
        } = row
        {
            let action_upper = action.to_uppercase();
            let action_color = match action_upper.as_str() {
                "BUY" | "COVER" => "\x1b[32m",
                "SELL" | "SHORT" => "\x1b[31m",
                _ => "\x1b[37m",
            };

            println!("| {:<10} | \x1b[36m{:<6}\x1b[0m | {}{:<6}\x1b[0m | {}{:>8.0}\x1b[0m | \x1b[37m{:>8.2}\x1b[0m | \x1b[32m{:>11.0}\x1b[0m | \x1b[31m{:>12.0}\x1b[0m | \x1b[33m{:>18.2}\x1b[0m |",
                date,
                ticker,
                action_color,
                action_upper,
                action_color,
                *quantity,
                *price,
                *long_shares,
                *short_shares,
                *position_value
            );
        }
    }
    println!("{}", header_border);
    println!("\n\n");
}
