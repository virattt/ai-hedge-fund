export interface MultiNodeDefinition {
  name: string;
  nodes: {
    componentName: string;
    offsetX: number;
    offsetY: number;
  }[];
  edges: {
    source: string;
    target: string;
  }[];
}

// List of all swarm names for easy reference
export const SWARM_NAMES = [
  "Value Investors",
  "Growth Investors", 
  "Contrarian Investors",
  "Technical Analysis Team",
  "Fundamental Analysis Team",
  "Macro Strategy Team",
  "All Agents"
] as const;

export const multiNodeDefinition: Record<string, MultiNodeDefinition> = {
  "Value Investors": {
    name: "Value Investors",
    nodes: [
      { componentName: "Portfolio Manager", offsetX: 0, offsetY: 0 },
      { componentName: "Ben Graham", offsetX: 400, offsetY: -250 },
      { componentName: "Charlie Munger", offsetX: 400, offsetY: 0 },
      { componentName: "Warren Buffett", offsetX: 400, offsetY: 250 },
      { componentName: "Text Output", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Portfolio Manager", target: "Ben Graham" },
      { source: "Portfolio Manager", target: "Charlie Munger" },
      { source: "Portfolio Manager", target: "Warren Buffett" },
      { source: "Ben Graham", target: "Text Output" },
      { source: "Charlie Munger", target: "Text Output" },
      { source: "Warren Buffett", target: "Text Output" },
    ],
  },
  "Growth Investors": {
    name: "Growth Investors",
    nodes: [
      { componentName: "Portfolio Manager", offsetX: 0, offsetY: 0 },
      { componentName: "Cathie Wood", offsetX: 400, offsetY: -200 },
      { componentName: "Peter Lynch", offsetX: 400, offsetY: 0 },
      { componentName: "Phil Fisher", offsetX: 400, offsetY: 200 },
      { componentName: "Text Output", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Portfolio Manager", target: "Cathie Wood" },
      { source: "Portfolio Manager", target: "Peter Lynch" },
      { source: "Portfolio Manager", target: "Phil Fisher" },
      { source: "Cathie Wood", target: "Text Output" },
      { source: "Peter Lynch", target: "Text Output" },
      { source: "Phil Fisher", target: "Text Output" },
    ],
  },
  "Contrarian Investors": {
    name: "Contrarian Investors",
    nodes: [
      { componentName: "Portfolio Manager", offsetX: 0, offsetY: 0 },
      { componentName: "Michael Burry", offsetX: 400, offsetY: -150 },
      { componentName: "Bill Ackman", offsetX: 400, offsetY: 150 },
      { componentName: "Text Output", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Portfolio Manager", target: "Michael Burry" },
      { source: "Portfolio Manager", target: "Bill Ackman" },
      { source: "Michael Burry", target: "Text Output" },
      { source: "Bill Ackman", target: "Text Output" },
    ],
  },
  "Technical Analysis Team": {
    name: "Technical Analysis Team",
    nodes: [
      { componentName: "Portfolio Manager", offsetX: 0, offsetY: 0 },
      { componentName: "Technical Analyst", offsetX: 400, offsetY: -150 },
      { componentName: "Sentiment Analyst", offsetX: 400, offsetY: 150 },
      { componentName: "Text Output", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Portfolio Manager", target: "Technical Analyst" },
      { source: "Portfolio Manager", target: "Sentiment Analyst" },
      { source: "Technical Analyst", target: "Text Output" },
      { source: "Sentiment Analyst", target: "Text Output" },
    ],
  },
  "Fundamental Analysis Team": {
    name: "Fundamental Analysis Team",
    nodes: [
      { componentName: "Portfolio Manager", offsetX: 0, offsetY: 0 },
      { componentName: "Fundamentals Analyst", offsetX: 400, offsetY: -200 },
      { componentName: "Valuation Analyst", offsetX: 400, offsetY: 0 },
      { componentName: "Aswath Damodaran", offsetX: 400, offsetY: 200 },
      { componentName: "Text Output", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Portfolio Manager", target: "Fundamentals Analyst" },
      { source: "Portfolio Manager", target: "Valuation Analyst" },
      { source: "Portfolio Manager", target: "Aswath Damodaran" },
      { source: "Fundamentals Analyst", target: "Text Output" },
      { source: "Valuation Analyst", target: "Text Output" },
      { source: "Aswath Damodaran", target: "Text Output" },
    ],
  },
  "Macro Strategy Team": {
    name: "Macro Strategy Team",
    nodes: [
      { componentName: "Portfolio Manager", offsetX: 0, offsetY: 0 },
      { componentName: "Stanley Druckenmiller", offsetX: 400, offsetY: -150 },
      { componentName: "Rakesh Jhunjhunwala", offsetX: 400, offsetY: 150 },
      { componentName: "Text Output", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Portfolio Manager", target: "Stanley Druckenmiller" },
      { source: "Portfolio Manager", target: "Rakesh Jhunjhunwala" },
      { source: "Stanley Druckenmiller", target: "Text Output" },
      { source: "Rakesh Jhunjhunwala", target: "Text Output" },
    ],
  },
  "All Agents": {
    name: "All Agents",
    nodes: [
      { componentName: "Portfolio Manager", offsetX: 0, offsetY: 0 },
      // Famous Investors - Left Column
      { componentName: "Warren Buffett", offsetX: 300, offsetY: -500 },
      { componentName: "Charlie Munger", offsetX: 300, offsetY: -400 },
      { componentName: "Ben Graham", offsetX: 300, offsetY: -300 },
      { componentName: "Peter Lynch", offsetX: 300, offsetY: -200 },
      { componentName: "Phil Fisher", offsetX: 300, offsetY: -100 },
      // Growth & Contrarian - Center Left
      { componentName: "Cathie Wood", offsetX: 500, offsetY: -500 },
      { componentName: "Michael Burry", offsetX: 500, offsetY: -400 },
      { componentName: "Bill Ackman", offsetX: 500, offsetY: -300 },
      { componentName: "Stanley Druckenmiller", offsetX: 500, offsetY: -200 },
      { componentName: "Rakesh Jhunjhunwala", offsetX: 500, offsetY: -100 },
      { componentName: "Aswath Damodaran", offsetX: 500, offsetY: 0 },
      // Analysts - Center Right
      { componentName: "Technical Analyst", offsetX: 700, offsetY: -400 },
      { componentName: "Fundamentals Analyst", offsetX: 700, offsetY: -300 },
      { componentName: "Sentiment Analyst", offsetX: 700, offsetY: -200 },
      { componentName: "Valuation Analyst", offsetX: 700, offsetY: -100 },
      // Output
      { componentName: "Text Output", offsetX: 900, offsetY: -250 },
    ],
    edges: [
      // Portfolio Manager to all agents
      { source: "Portfolio Manager", target: "Warren Buffett" },
      { source: "Portfolio Manager", target: "Charlie Munger" },
      { source: "Portfolio Manager", target: "Ben Graham" },
      { source: "Portfolio Manager", target: "Peter Lynch" },
      { source: "Portfolio Manager", target: "Phil Fisher" },
      { source: "Portfolio Manager", target: "Cathie Wood" },
      { source: "Portfolio Manager", target: "Michael Burry" },
      { source: "Portfolio Manager", target: "Bill Ackman" },
      { source: "Portfolio Manager", target: "Stanley Druckenmiller" },
      { source: "Portfolio Manager", target: "Rakesh Jhunjhunwala" },
      { source: "Portfolio Manager", target: "Aswath Damodaran" },
      { source: "Portfolio Manager", target: "Technical Analyst" },
      { source: "Portfolio Manager", target: "Fundamentals Analyst" },
      { source: "Portfolio Manager", target: "Sentiment Analyst" },
      { source: "Portfolio Manager", target: "Valuation Analyst" },
      // All agents to output
      { source: "Warren Buffett", target: "Text Output" },
      { source: "Charlie Munger", target: "Text Output" },
      { source: "Ben Graham", target: "Text Output" },
      { source: "Peter Lynch", target: "Text Output" },
      { source: "Phil Fisher", target: "Text Output" },
      { source: "Cathie Wood", target: "Text Output" },
      { source: "Michael Burry", target: "Text Output" },
      { source: "Bill Ackman", target: "Text Output" },
      { source: "Stanley Druckenmiller", target: "Text Output" },
      { source: "Rakesh Jhunjhunwala", target: "Text Output" },
      { source: "Aswath Damodaran", target: "Text Output" },
      { source: "Technical Analyst", target: "Text Output" },
      { source: "Fundamentals Analyst", target: "Text Output" },
      { source: "Sentiment Analyst", target: "Text Output" },
      { source: "Valuation Analyst", target: "Text Output" },
    ],
  },
};

export function getMultiNodeDefinition(name: string): MultiNodeDefinition | null {
  return multiNodeDefinition[name] || null;
}

export function isMultiNodeComponent(componentName: string): boolean {
  return componentName in multiNodeDefinition;
}

export function isSwarmComponent(componentName: string): boolean {
  return SWARM_NAMES.includes(componentName as typeof SWARM_NAMES[number]);
} 