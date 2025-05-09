"""Constants and utilities related to analysts configuration."""

from src.agents.ben_graham import ben_graham_agent
from src.agents.bill_ackman import bill_ackman_agent
from src.agents.cathie_wood import cathie_wood_agent
from src.agents.charlie_munger import charlie_munger_agent
from src.agents.fundamentals import fundamentals_agent
from src.agents.michael_burry import michael_burry_agent
from src.agents.phil_fisher import phil_fisher_agent
from src.agents.peter_lynch import peter_lynch_agent
from src.agents.sentiment import sentiment_agent
from src.agents.stanley_druckenmiller import stanley_druckenmiller_agent
from src.agents.technicals import technical_analyst_agent
from src.agents.valuation import valuation_agent
from src.agents.warren_buffett import warren_buffett_agent

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
    "michael_burry": {
        "display_name": "Michael Burry",
        "agent_func": michael_burry_agent,
        "order": 4,
    },
    "peter_lynch": {
        "display_name": "Peter Lynch",
        "agent_func": peter_lynch_agent,
        "order": 5,
    },
    "phil_fisher": {
        "display_name": "Phil Fisher",
        "agent_func": phil_fisher_agent,
        "order": 6,
    },
    "stanley_druckenmiller": {
        "display_name": "Stanley Druckenmiller",
        "agent_func": stanley_druckenmiller_agent,
        "order": 7,
    },
    "warren_buffett": {
        "display_name": "Warren Buffett",
        "agent_func": warren_buffett_agent,
        "order": 8,
    },
    "technical_analyst": {
        "display_name": "Technical Analyst",
        "agent_func": technical_analyst_agent,
        "order": 9,
    },
    "fundamentals_analyst": {
        "display_name": "Fundamentals Analyst",
        "agent_func": fundamentals_agent,
        "order": 10,
    },
    "sentiment_analyst": {
        "display_name": "Sentiment Analyst",
        "agent_func": sentiment_agent,
        "order": 11,
    },
    "valuation_analyst": {
        "display_name": "Valuation Analyst",
        "agent_func": valuation_agent,
        "order": 12,
    },
}

# Derive ANALYST_ORDER from ANALYST_CONFIG for backwards compatibility
ANALYST_ORDER = [(config["display_name"], key) for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: x[1]["order"])]


def get_analyst_nodes():
    """Get the mapping of analyst keys to their (node_name, agent_func) tuples."""
    return {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}
