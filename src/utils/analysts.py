"""Constants and utilities related to analysts configuration."""

from agents.ben_graham import ben_graham_agent
from agents.bill_ackman import bill_ackman_agent
from agents.cathie_wood import cathie_wood_agent
from agents.charlie_munger import charlie_munger_agent
from agents.fundamentals import fundamentals_agent
from agents.sentiment import sentiment_agent
from agents.stanley_druckenmiller import stanley_druckenmiller_agent
from agents.technicals import technical_analyst_agent
from agents.chart_analysis import chart_analysis_agent  # Updated import
from agents.valuation import valuation_agent
from agents.warren_buffett import warren_buffett_agent

# Define analyst configuration - single source of truth
ANALYST_CONFIG = {
    "ben_graham": {
        "display_name": "Ben Graham",
        "agent_func": ben_graham_agent,
        "order": 0,
    },
    "bill_ackman": {
        "display_name": "Bill Ackman",
        "agent_func": bill_ackman_agent,
        "order": 1,
    },
    "cathie_wood": {
        "display_name": "Cathie Wood",
        "agent_func": cathie_wood_agent,
        "order": 2,
    },
    "charlie_munger": {
        "display_name": "Charlie Munger",
        "agent_func": charlie_munger_agent,
        "order": 3,
    },
    "stanley_druckenmiller": {
        "display_name": "Stanley Druckenmiller",
        "agent_func": stanley_druckenmiller_agent,
        "order": 4,
    },
    "warren_buffett": {
        "display_name": "Warren Buffett",
        "agent_func": warren_buffett_agent,
        "order": 5,
    },
    "technical_analyst": {
        "display_name": "Technical Analyst",
        "agent_func": technical_analyst_agent,
        "order": 6,
    },
    "fundamentals_analyst": {
        "display_name": "Fundamentals Analyst",
        "agent_func": fundamentals_agent,
        "order": 7,
    },
    "sentiment_analyst": {
        "display_name": "Sentiment Analyst",
        "agent_func": sentiment_agent,
        "order": 8,
    },
    "valuation_analyst": {
        "display_name": "Valuation Analyst",
        "agent_func": valuation_agent,
        "order": 9,
    },
    "chart_analysis": {  # Updated key
        "display_name": "Chart Analysis",  # Updated display name
        "agent_func": chart_analysis_agent,  # Updated function reference
        "order": 10,
    },
}

# Derive ANALYST_ORDER from ANALYST_CONFIG for backwards compatibility
ANALYST_ORDER = [(config["display_name"], key) for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: x[1]["order"])]

# Ensure all analysts are included in the order
all_analysts = set(ANALYST_CONFIG.keys())
analysts_in_order = set(key for _, key in ANALYST_ORDER)

# Add any missing analysts to the order
if all_analysts != analysts_in_order:
    for key in all_analysts - analysts_in_order:
        ANALYST_ORDER.append((ANALYST_CONFIG[key]["display_name"], key))


def get_analyst_nodes():
    """Get the mapping of analyst keys to their (node_name, agent_func) tuples."""
    return {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}
