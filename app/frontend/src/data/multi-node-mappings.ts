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
      { componentName: "Stock Input", offsetX: 0, offsetY: 0 },
      { componentName: "Ben Graham", offsetX: 400, offsetY: -400 },
      { componentName: "Charlie Munger", offsetX: 400, offsetY: 0 },
      { componentName: "Warren Buffett", offsetX: 400, offsetY: 400 },
      { componentName: "Portfolio Manager", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Stock Input", target: "Ben Graham" },
      { source: "Stock Input", target: "Charlie Munger" },
      { source: "Stock Input", target: "Warren Buffett" },
      { source: "Ben Graham", target: "Portfolio Manager" },
      { source: "Charlie Munger", target: "Portfolio Manager" },
      { source: "Warren Buffett", target: "Portfolio Manager" },
    ],
  },
  "Data Wizards": {
    name: "Data Wizards",
    nodes: [
      { componentName: "Stock Input", offsetX: 0, offsetY: 0 },
      { componentName: "Technical Analyst", offsetX: 400, offsetY: -550 },
      { componentName: "Fundamentals Analyst", offsetX: 400, offsetY: -200 },
      { componentName: "Sentiment Analyst", offsetX: 400, offsetY: 150 },
      { componentName: "Valuation Analyst", offsetX: 400, offsetY: 500 },
      { componentName: "Portfolio Manager", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Stock Input", target: "Technical Analyst" },
      { source: "Stock Input", target: "Fundamentals Analyst" },
      { source: "Stock Input", target: "Sentiment Analyst" },
      { source: "Stock Input", target: "Valuation Analyst" },
      { source: "Technical Analyst", target: "Portfolio Manager" },
      { source: "Fundamentals Analyst", target: "Portfolio Manager" },
      { source: "Sentiment Analyst", target: "Portfolio Manager" },
      { source: "Valuation Analyst", target: "Portfolio Manager" },

    ],
  },
  "Market Mavericks": {
    name: "Market Mavericks",
    nodes: [
      { componentName: "Stock Input", offsetX: 0, offsetY: 0 },
      { componentName: "Michael Burry", offsetX: 400, offsetY: -400 },
      { componentName: "Bill Ackman", offsetX: 400, offsetY: 0 },
      { componentName: "Stanley Druckenmiller", offsetX: 400, offsetY: 400 },
      { componentName: "Portfolio Manager", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Stock Input", target: "Michael Burry" },
      { source: "Stock Input", target: "Bill Ackman" },
      { source: "Stock Input", target: "Stanley Druckenmiller" },
      { source: "Michael Burry", target: "Portfolio Manager" },
      { source: "Bill Ackman", target: "Portfolio Manager" },
      { source: "Stanley Druckenmiller", target: "Portfolio Manager" },
    ],
  },
};

export function getMultiNodeDefinition(name: string): MultiNodeDefinition | null {
  return multiNodeDefinition[name] || null;
}

export function isMultiNodeComponent(componentName: string): boolean {
  return componentName in multiNodeDefinition;
} 