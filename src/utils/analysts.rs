// Source: src/utils/analysts.py
//! Registry containing details, descriptions, and metadata for all available AI stock analysts.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AnalystConfig {
    pub display_name: String,
    pub description: String,
    pub investing_style: String,
    pub r#type: String,
    pub order: u32,
}

/// Retrieves the complete list of analysts for API and CLI menus.
pub fn get_analysts_list() -> Vec<AnalystConfig> {
    vec![
        AnalystConfig {
            display_name: "Aswath Damodaran".to_string(),
            description: "The Dean of Valuation".to_string(),
            investing_style: "Focuses on intrinsic value and financial metrics to assess investment opportunities through rigorous valuation analysis.".to_string(),
            r#type: "analyst".to_string(),
            order: 0,
        },
        AnalystConfig {
            display_name: "Ben Graham".to_string(),
            description: "The Father of Value Investing".to_string(),
            investing_style: "Emphasizes a margin of safety and invests in undervalued companies with strong fundamentals through systematic value analysis.".to_string(),
            r#type: "analyst".to_string(),
            order: 1,
        },
        AnalystConfig {
            display_name: "Bill Ackman".to_string(),
            description: "The Activist Investor".to_string(),
            investing_style: "Seeks to influence management and unlock value through strategic activism and contrarian investment positions.".to_string(),
            r#type: "analyst".to_string(),
            order: 2,
        },
        AnalystConfig {
            display_name: "Cathie Wood".to_string(),
            description: "The Queen of Growth Investing".to_string(),
            investing_style: "Focuses on disruptive innovation and growth, investing in companies that are leading technological advancements and market disruption.".to_string(),
            r#type: "analyst".to_string(),
            order: 3,
        },
        AnalystConfig {
            display_name: "Charlie Munger".to_string(),
            description: "The Rational Thinker".to_string(),
            investing_style: "Advocates for value investing with a focus on quality businesses and long-term growth through rational decision-making.".to_string(),
            r#type: "analyst".to_string(),
            order: 4,
        },
        AnalystConfig {
            display_name: "Michael Burry".to_string(),
            description: "The Big Short Contrarian".to_string(),
            investing_style: "Makes contrarian bets, often shorting overvalued markets and investing in undervalued assets through deep fundamental analysis.".to_string(),
            r#type: "analyst".to_string(),
            order: 5,
        },
        AnalystConfig {
            display_name: "Mohnish Pabrai".to_string(),
            description: "The Dhandho Investor".to_string(),
            investing_style: "Focuses on value investing and long-term growth through fundamental analysis and a margin of safety.".to_string(),
            r#type: "analyst".to_string(),
            order: 6,
        },
        AnalystConfig {
            display_name: "Nassim Taleb".to_string(),
            description: "The Black Swan Risk Analyst".to_string(),
            investing_style: "Focuses on tail risk, antifragility, and asymmetric payoffs. Uses barbell strategy, avoids fragile companies via negativa, and seeks convex positions with limited downside and unlimited upside.".to_string(),
            r#type: "analyst".to_string(),
            order: 7,
        },
        AnalystConfig {
            display_name: "Peter Lynch".to_string(),
            description: "The 10-Bagger Investor".to_string(),
            investing_style: "Invests in companies with understandable business models and strong growth potential using the 'buy what you know' strategy.".to_string(),
            r#type: "analyst".to_string(),
            order: 8,
        },
        AnalystConfig {
            display_name: "Phil Fisher".to_string(),
            description: "The Scuttlebutt Investor".to_string(),
            investing_style: "Emphasizes investing in companies with strong management and innovative products, focusing on long-term growth through scuttlebutt research.".to_string(),
            r#type: "analyst".to_string(),
            order: 9,
        },
        AnalystConfig {
            display_name: "Rakesh Jhunjhunwala".to_string(),
            description: "The Big Bull Of India".to_string(),
            investing_style: "Leverages macroeconomic insights to invest in high-growth sectors, particularly within emerging markets and domestic opportunities.".to_string(),
            r#type: "analyst".to_string(),
            order: 10,
        },
        AnalystConfig {
            display_name: "Stanley Druckenmiller".to_string(),
            description: "The Macro Investor".to_string(),
            investing_style: "Focuses on macroeconomic trends, making large bets on currencies, commodities, and interest rates through top-down analysis.".to_string(),
            r#type: "analyst".to_string(),
            order: 11,
        },
        AnalystConfig {
            display_name: "Warren Buffett".to_string(),
            description: "The Oracle of Omaha".to_string(),
            investing_style: "Seeks companies with strong fundamentals and competitive advantages through value investing and long-term ownership.".to_string(),
            r#type: "analyst".to_string(),
            order: 12,
        },
        AnalystConfig {
            display_name: "Technical Analyst".to_string(),
            description: "Chart Pattern Specialist".to_string(),
            investing_style: "Focuses on chart patterns and market trends to make investment decisions, often using technical indicators and price action analysis.".to_string(),
            r#type: "analyst".to_string(),
            order: 13,
        },
        AnalystConfig {
            display_name: "Fundamentals Analyst".to_string(),
            description: "Financial Statement Specialist".to_string(),
            investing_style: "Delves into financial statements and economic indicators to assess the intrinsic value of companies through fundamental analysis.".to_string(),
            r#type: "analyst".to_string(),
            order: 14,
        },
        AnalystConfig {
            display_name: "Growth Analyst".to_string(),
            description: "Growth Specialist".to_string(),
            investing_style: "Analyzes growth trends and valuation to identify growth opportunities through growth analysis.".to_string(),
            r#type: "analyst".to_string(),
            order: 15,
        },
        AnalystConfig {
            display_name: "News Sentiment Analyst".to_string(),
            description: "News Sentiment Specialist".to_string(),
            investing_style: "Analyzes news sentiment to predict market movements and identify opportunities through news analysis.".to_string(),
            r#type: "analyst".to_string(),
            order: 16,
        },
        AnalystConfig {
            display_name: "Sentiment Analyst".to_string(),
            description: "Market Sentiment Specialist".to_string(),
            investing_style: "Gauges market sentiment and investor behavior to predict market movements and identify opportunities through behavioral analysis.".to_string(),
            r#type: "analyst".to_string(),
            order: 17,
        },
        AnalystConfig {
            display_name: "Valuation Analyst".to_string(),
            description: "Company Valuation Specialist".to_string(),
            investing_style: "Specializes in determining the fair value of companies, using various valuation models and financial metrics for investment decisions.".to_string(),
            r#type: "analyst".to_string(),
            order: 18,
        },
    ]
}

/// Returns a mapping of analyst identifiers to their internal node execution tags.
pub fn get_analyst_nodes() -> HashMap<String, String> {
    let mut map = HashMap::new();
    map.insert(
        "aswath_damodaran".to_string(),
        "aswath_damodaran_agent".to_string(),
    );
    map.insert("ben_graham".to_string(), "ben_graham_agent".to_string());
    map.insert("bill_ackman".to_string(), "bill_ackman_agent".to_string());
    map.insert("cathie_wood".to_string(), "cathie_wood_agent".to_string());
    map.insert(
        "charlie_munger".to_string(),
        "charlie_munger_agent".to_string(),
    );
    map.insert(
        "michael_burry".to_string(),
        "michael_burry_agent".to_string(),
    );
    map.insert(
        "mohnish_pabrai".to_string(),
        "mohnish_pabrai_agent".to_string(),
    );
    map.insert("nassim_taleb".to_string(), "nassim_taleb_agent".to_string());
    map.insert("peter_lynch".to_string(), "peter_lynch_agent".to_string());
    map.insert("phil_fisher".to_string(), "phil_fisher_agent".to_string());
    map.insert(
        "rakesh_jhunjhunwala".to_string(),
        "rakesh_jhunjhunwala_agent".to_string(),
    );
    map.insert(
        "stanley_druckenmiller".to_string(),
        "stanley_druckenmiller_agent".to_string(),
    );
    map.insert(
        "warren_buffett".to_string(),
        "warren_buffett_agent".to_string(),
    );
    map.insert(
        "technical_analyst".to_string(),
        "technical_analyst_agent".to_string(),
    );
    map.insert(
        "fundamentals_analyst".to_string(),
        "fundamentals_analyst_agent".to_string(),
    );
    map.insert(
        "growth_analyst".to_string(),
        "growth_analyst_agent".to_string(),
    );
    map.insert(
        "news_sentiment_analyst".to_string(),
        "news_sentiment_agent".to_string(),
    );
    map.insert(
        "sentiment_analyst".to_string(),
        "sentiment_analyst_agent".to_string(),
    );
    map.insert(
        "valuation_analyst".to_string(),
        "valuation_analyst_agent".to_string(),
    );
    map
}
