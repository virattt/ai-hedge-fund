import { AppNode } from "@/nodes/types";
import { agents } from "./agents";

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
  // Dynamic node creation for all agents
  ...agents.reduce((acc, agent) => {
    acc[agent.display_name] = {
      createNode: (position: { x: number, y: number }): AppNode => ({
        id: agent.key,
        type: "agent-node",
        position,
        data: {
          name: agent.display_name,
          description: agent.description || "",
          status: "Idle",
        },
      }),
    };
    return acc;
  }, {} as Record<string, NodeTypeDefinition>),
};

export function getNodeTypeDefinition(componentName: string): NodeTypeDefinition | null {
  return nodeTypeDefinitions[componentName] || null;
} 