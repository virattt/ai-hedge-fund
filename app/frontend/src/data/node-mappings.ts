import { AppNode } from "@/nodes/types";
import { Agent, getAgents } from "./agents";

// Map of sidebar item names to node creation functions
export interface NodeTypeDefinition {
  createNode: (position: { x: number, y: number }) => AppNode;
}

// Cache for node type definitions to avoid repeated API calls
let nodeTypeDefinitionsCache: Record<string, NodeTypeDefinition> | null = null;

// Define base node creation functions (non-agent nodes)
const baseNodeTypeDefinitions: Record<string, NodeTypeDefinition> = {
  "Portfolio Manager": {
    createNode: (position: { x: number, y: number }): AppNode => ({
      id: `portfolio-manager-node`,
      type: "portfolio-manager-node",
      position,
      data: {
        name: "Portfolio Manager",
        description: "Start Node",
        status: "Idle",
      },
    }),
  },
  "JSON Output": {
    createNode: (position: { x: number, y: number }): AppNode => ({
      id: `json-output-node`,
      type: "json-output-node",
      position,
      data: {
        name: "JSON Output",
        description: "End Node",
        status: "Idle",
      },
    }),
  },
  "Investment Report": {
    createNode: (position: { x: number, y: number }): AppNode => ({
      id: `investment-report-node`,
      type: "investment-report-node",
      position,
      data: {
        name: "Investment Report",
        description: "End Node",
        status: "Idle",
      },
    }),
  },
};

/**
 * Get all node type definitions, including agents fetched from the backend
 */
const getNodeTypeDefinitions = async (): Promise<Record<string, NodeTypeDefinition>> => {
  if (nodeTypeDefinitionsCache) {
    return nodeTypeDefinitionsCache;
  }

  const agents = await getAgents();
  
  // Create agent node definitions
  const agentNodeDefinitions = agents.reduce((acc: Record<string, NodeTypeDefinition>, agent: Agent) => {
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
  }, {});

  // Combine base and agent definitions
  nodeTypeDefinitionsCache = {
    ...baseNodeTypeDefinitions,
    ...agentNodeDefinitions,
  };

  return nodeTypeDefinitionsCache;
};

export async function getNodeTypeDefinition(componentName: string): Promise<NodeTypeDefinition | null> {
  const nodeTypeDefinitions = await getNodeTypeDefinitions();
  return nodeTypeDefinitions[componentName] || null;
}

// Get the node ID that would be generated for a component
export async function getNodeIdForComponent(componentName: string): Promise<string | null> {
  const nodeTypeDefinition = await getNodeTypeDefinition(componentName);
  if (!nodeTypeDefinition) {
    return null;
  }
  
  // Extract ID by creating a temporary node (position doesn't matter for ID extraction)
  const tempNode = nodeTypeDefinition.createNode({ x: 0, y: 0 });
  return tempNode.id;
}

/**
 * Clear the node type definitions cache - useful for testing or when you want to force a refresh
 */
export const clearNodeTypeDefinitionsCache = () => {
  nodeTypeDefinitionsCache = null;
}; 