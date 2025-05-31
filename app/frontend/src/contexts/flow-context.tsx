import { getMultiNodeDefinition, isMultiNodeComponent } from '@/data/multi-node-mappings';
import { getNodeIdForComponent, getNodeTypeDefinition } from '@/data/node-mappings';
import { useReactFlow, XYPosition } from '@xyflow/react';
import { createContext, ReactNode, useCallback, useContext } from 'react';

interface FlowContextType {
  addComponentToFlow: (componentName: string) => void;
}

const FlowContext = createContext<FlowContextType | null>(null);

export function useFlowContext() {
  const context = useContext(FlowContext);
  if (!context) {
    throw new Error('useFlowContext must be used within a FlowProvider');
  }
  return context;
}

interface FlowProviderProps {
  children: ReactNode;
}

export function FlowProvider({ children }: FlowProviderProps) {
  const reactFlowInstance = useReactFlow();

  // Calculate viewport center position with optional randomness
  const getViewportPosition = useCallback((addRandomness = false): XYPosition => {
    let position: XYPosition = { x: 0, y: 0 }; // Default position
    
    try {
      const { zoom, x, y } = reactFlowInstance.getViewport();
      
      // Get the React Flow container dimensions instead of window dimensions
      const flowContainer = document.querySelector('.react-flow__viewport')?.parentElement;
      const containerWidth = flowContainer?.clientWidth || window.innerWidth;
      const containerHeight = flowContainer?.clientHeight || window.innerHeight;
      
      position = {
        x: (containerWidth / 2 - x) / zoom,
        y: (containerHeight / 2 - y) / zoom,
      };
    } catch (err) {
      console.warn('Could not get viewport', err);
    }
    
    if (addRandomness) {
      position.x += Math.random() * 100 - 50;
      position.y = 0;
    }
    
    return position;
  }, [reactFlowInstance]);

  // Add a single node to the flow
  const addSingleNodeToFlow = useCallback((componentName: string) => {
    const nodeTypeDefinition = getNodeTypeDefinition(componentName);
    if (!nodeTypeDefinition) {
      console.warn(`No node type definition found for component: ${componentName}`);
      return;
    }

    const position = getViewportPosition(true);
    const newNode = nodeTypeDefinition.createNode(position);
    reactFlowInstance.setNodes((nodes) => [...nodes, newNode]);
  }, [reactFlowInstance, getViewportPosition]);

  // Add a multi node (group of nodes with edges) to the flow
  const addMultipleNodesToFlow = useCallback((name: string) => {
    const multiNodeDefinition = getMultiNodeDefinition(name);
    if (!multiNodeDefinition) {
      console.warn(`No multi node definition found for: ${name}`);
      return;
    }

    const basePosition = getViewportPosition();

    // Calculate bounding box of all nodes to center the group
    const nodePositions = multiNodeDefinition.nodes.map(node => ({
      x: node.offsetX,
      y: node.offsetY
    }));
    
    const minX = Math.min(...nodePositions.map(pos => pos.x));
    const maxX = Math.max(...nodePositions.map(pos => pos.x));
    const minY = Math.min(...nodePositions.map(pos => pos.y));
    const maxY = Math.max(...nodePositions.map(pos => pos.y));
    
    // Center the group by adjusting base position
    const groupCenterX = (minX + maxX) / 2;
    const groupCenterY = (minY + maxY) / 2;
    
    const adjustedBasePosition = {
      x: basePosition.x - groupCenterX,
      y: basePosition.y - groupCenterY,
    };

    // Create nodes
    const newNodes = multiNodeDefinition.nodes.map((nodeConfig) => {
      const nodeTypeDefinition = getNodeTypeDefinition(nodeConfig.componentName);
      if (!nodeTypeDefinition) {
        console.warn(`No node type definition found for: ${nodeConfig.componentName}`);
        return null;
      }

      const position = {
        x: adjustedBasePosition.x + nodeConfig.offsetX,
        y: adjustedBasePosition.y + nodeConfig.offsetY,
      };

      return nodeTypeDefinition.createNode(position);
    }).filter((node): node is NonNullable<typeof node> => node !== null);

    // Create edges
    const newEdges = multiNodeDefinition.edges.map((edgeConfig) => {
      const sourceNodeId = getNodeIdForComponent(edgeConfig.source);
      const targetNodeId = getNodeIdForComponent(edgeConfig.target);
      
      if (!sourceNodeId || !targetNodeId) {
        console.warn(`Could not resolve node IDs for edge: ${edgeConfig.source} -> ${edgeConfig.target}`);
        return null;
      }
      
      return {
        id: `${sourceNodeId}-${targetNodeId}`,
        source: sourceNodeId,
        target: targetNodeId,
      };
    }).filter((edge): edge is NonNullable<typeof edge> => edge !== null);

    // Add nodes and edges to flow
    reactFlowInstance.setNodes((nodes) => [...nodes, ...newNodes]);
    reactFlowInstance.setEdges((edges) => [...edges, ...newEdges]);
  }, [reactFlowInstance, getViewportPosition]);

  // Main entry point - route to single node or multi node
  const addComponentToFlow = useCallback((componentName: string) => {
    if (isMultiNodeComponent(componentName)) {
      addMultipleNodesToFlow(componentName);
    } else {
      addSingleNodeToFlow(componentName);
    }
  }, [addMultipleNodesToFlow, addSingleNodeToFlow]);

  const value = {
    addComponentToFlow,
  };

  return (
    <FlowContext.Provider value={value}>
      {children}
    </FlowContext.Provider>
  );
} 