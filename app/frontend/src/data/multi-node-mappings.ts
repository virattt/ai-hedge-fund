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

export const multiNodeDefinition: Record<string, MultiNodeDefinition> = {
  "Value Investors": {
    name: "Value Investors",
    nodes: [
      { componentName: "Text Input", offsetX: 0, offsetY: 0 },
      { componentName: "Ben Graham", offsetX: 400, offsetY: -250 },
      { componentName: "Charlie Munger", offsetX: 400, offsetY: 0 },
      { componentName: "Warren Buffett", offsetX: 400, offsetY: 250 },
      { componentName: "Text Output", offsetX: 800, offsetY: 0 },
    ],
    edges: [
      { source: "Text Input", target: "Ben Graham" },
      { source: "Text Input", target: "Charlie Munger" },
      { source: "Text Input", target: "Warren Buffett" },
      { source: "Ben Graham", target: "Text Output" },
      { source: "Charlie Munger", target: "Text Output" },
      { source: "Warren Buffett", target: "Text Output" },
    ],
  },
};

export function getMultiNodeDefinition(name: string): MultiNodeDefinition | null {
  return multiNodeDefinition[name] || null;
}

export function isMultiNodeComponent(componentName: string): boolean {
  return componentName in multiNodeDefinition;
} 