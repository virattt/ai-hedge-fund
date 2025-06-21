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

const multiNodeDefinition: Record<string, MultiNodeDefinition> = {
  "Value Investors": {
    name: "Value Investors",
    nodes: [
      { componentName: "Portfolio Manager", offsetX: 0, offsetY: 0 },
      { componentName: "Ben Graham", offsetX: 400, offsetY: -300 },
      { componentName: "Charlie Munger", offsetX: 400, offsetY: 0 },
      { componentName: "Warren Buffett", offsetX: 400, offsetY: 300 },
      { componentName: "Investment Report", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Portfolio Manager", target: "Ben Graham" },
      { source: "Portfolio Manager", target: "Charlie Munger" },
      { source: "Portfolio Manager", target: "Warren Buffett" },
      { source: "Ben Graham", target: "Investment Report" },
      { source: "Charlie Munger", target: "Investment Report" },
      { source: "Warren Buffett", target: "Investment Report" },
    ],
  },
  "Data Wizards": {
    name: "Data Wizards",
    nodes: [
      { componentName: "Portfolio Manager", offsetX: 0, offsetY: 0 },
      { componentName: "Technical Analyst", offsetX: 400, offsetY: -550 },
      { componentName: "Fundamentals Analyst", offsetX: 400, offsetY: -200 },
      { componentName: "Sentiment Analyst", offsetX: 400, offsetY: 150 },
      { componentName: "Valuation Analyst", offsetX: 400, offsetY: 500 },
      { componentName: "Investment Report", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Portfolio Manager", target: "Technical Analyst" },
      { source: "Portfolio Manager", target: "Fundamentals Analyst" },
      { source: "Portfolio Manager", target: "Sentiment Analyst" },
      { source: "Portfolio Manager", target: "Valuation Analyst" },
      { source: "Technical Analyst", target: "Investment Report" },
      { source: "Fundamentals Analyst", target: "Investment Report" },
      { source: "Sentiment Analyst", target: "Investment Report" },
      { source: "Valuation Analyst", target: "Investment Report" },
    ],
  },
};

export function getMultiNodeDefinition(name: string): MultiNodeDefinition | null {
  return multiNodeDefinition[name] || null;
}

export function isMultiNodeComponent(componentName: string): boolean {
  return componentName in multiNodeDefinition;
} 