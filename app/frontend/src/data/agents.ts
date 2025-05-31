export interface AgentItem {
  key: string;
  display_name: string;
  description?: string;
  order: number;
}

export const agents: AgentItem[] = [
  {
    "key": "aswath_damodaran",
    "display_name": "Aswath Damodaran",
    "description": "The Dean of Valuation",
    "order": 0
  },
  {
    "key": "ben_graham",
    "display_name": "Ben Graham",
    "description": "The Father of Value Investing",
    "order": 1
  },
  {
    "key": "bill_ackman",
    "display_name": "Bill Ackman",
    "description": "The Activist Investor",
    "order": 2
  },
  {
    "key": "cathie_wood",
    "display_name": "Cathie Wood",
    "description": "The Queen of Growth Investing",
    "order": 3
  },
  {
    "key": "charlie_munger",
    "display_name": "Charlie Munger",
    "description": "The Rational Thinker",
    "order": 4
  },
  {
    "key": "michael_burry",
    "display_name": "Michael Burry",
    "description": "The Big Short Contrarian",
    "order": 5
  },
  {
    "key": "peter_lynch",
    "display_name": "Peter Lynch",
    "description": "The 10-Bagger Investor",
    "order": 6
  },
  {
    "key": "phil_fisher",
    "display_name": "Phil Fisher",
    "description": "The Scuttlebutt Investor",
    "order": 7
  },
  {
    "key": "rakesh_jhunjhunwala",
    "display_name": "Rakesh Jhunjhunwala",
    "description": "The Big Bull Of India",
    "order": 8
  },
  {
    "key": "stanley_druckenmiller",
    "display_name": "Stanley Druckenmiller",
    "description": "The Macro Investor",
    "order": 9
  },
  {
    "key": "warren_buffett",
    "display_name": "Warren Buffett",
    "description": "The Oracle of Omaha",
    "order": 10
  },
  {
    "key": "technical_analyst",
    "display_name": "Technical Analyst",
    "description": "Chart Pattern Specialist",
    "order": 11
  },
  {
    "key": "fundamentals_analyst",
    "display_name": "Fundamentals Analyst",
    "description": "Financial Statement Specialist",
    "order": 12
  },
  {
    "key": "sentiment_analyst",
    "display_name": "Sentiment Analyst",
    "description": "Market Sentiment Specialist",
    "order": 13
  },
  {
    "key": "valuation_analyst",
    "display_name": "Valuation Analyst",
    "description": "Company Valuation Specialist",
    "order": 14
  },
  
];

// Get agent by key
export function getAgentByKey(key: string): AgentItem | undefined {
  return agents.find(agent => agent.key === key);
}

// Get default agent to use
export const defaultAgent = agents.find(agent => agent.key === "warren_buffett") || null; 
