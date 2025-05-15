import { AppNode } from "@/nodes/types";

// Map of sidebar item names to node creation functions
export interface NodeTypeDefinition {
  createNode: (position: { x: number, y: number }) => AppNode;
}

// Define node creation functions for each type
const nodeTypeDefinitions: Record<string, NodeTypeDefinition> = {
  "Text Input": {
    createNode: (position: { x: number, y: number }): AppNode => ({
      id: `text-input-node`,
      type: "input-node",
      position,
      data: {
        name: "Input",
        description: "Start Node",
        status: "Idle",
      },
    }),
  },
  "Text Output": {
    createNode: (position: { x: number, y: number }): AppNode => ({
      id: `text-output-node`,
      type: "output-node",
      position,
      data: {
        name: "Output",
        description: "Output Node",
        status: "Idle",
      },
    }),
  },
  "Ben Graham": {
    createNode: (position: { x: number, y: number }): AppNode => ({
      id: `ben_graham`,
      type: "agent-node",
      position,
      data: {
        name: "Ben Graham",
        description: "The Father of Value Investing",
        status: "Idle",
      },
    }),
  },
  "Charlie Munger": {
    createNode: (position: { x: number, y: number }): AppNode => ({
      id: `charlie_munger`,
      type: "agent-node",
      position,
      data: {
        name: "Charlie Munger",
        description: "The Abominable No-Man",
        status: "Idle",
      },
    }),
  },
  "Warren Buffett": {
    createNode: (position: { x: number, y: number }): AppNode => ({
      id: `warren_buffett`,
      type: "agent-node", 
      position,
      data: {
        name: "Warren Buffett",
        description: "The Oracle of Omaha",
        status: "Idle",
      },
    }),
  },
};

export function getNodeTypeDefinition(componentName: string): NodeTypeDefinition | null {
  return nodeTypeDefinitions[componentName] || null;
} 