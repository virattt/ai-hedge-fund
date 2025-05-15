import { getNodeTypeDefinition } from '@/data/node-mappings';
import { useReactFlow, XYPosition } from '@xyflow/react';
import { createContext, ReactNode, useCallback, useContext } from 'react';

interface FlowContextType {
  addNodeFromComponent: (componentName: string) => void;
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

/**
 * Generate a unique ID string
 */
function generateId(prefix: string = ''): string {
  return `${prefix}${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 10)}`;
}

export function FlowProvider({ children }: FlowProviderProps) {
  const reactFlowInstance = useReactFlow();

  // Add a node to the flow from a component in the sidebar
  const addNodeFromComponent = useCallback((componentName: string) => {
    const nodeTypeDefinition = getNodeTypeDefinition(componentName);
    if (!nodeTypeDefinition) {
      console.warn(`No node type definition found for component: ${componentName}`);
      return;
    }

    // Generate a unique ID for the new node
    // const uniqueId = generateId();
    
    // Calculate center viewport position
    let position: XYPosition = { x: 100, y: 100 }; // Default position
    
    // Try to get the viewport center position
    try {
      const { zoom, x, y } = reactFlowInstance.getViewport();
      
      // Calculate a position in the viewport
      // Get the window dimensions
      const windowWidth = window.innerWidth;
      const windowHeight = window.innerHeight;
      
      position = {
        x: (windowWidth / 2 - x) / zoom,
        y: (windowHeight / 2 - y) / zoom,
      };
    } catch (err) {
      console.warn('Could not get viewport', err);
    }
    
    // Add some randomness to prevent perfect overlap if multiple nodes are added
    position.x += Math.random() * 100 - 50;
    position.y += Math.random() * 100 - 50;
    
    // Create the new node
    const newNode = nodeTypeDefinition.createNode(position);
    
    // Add the new node to the flow
    reactFlowInstance.setNodes((nodes) => [...nodes, newNode]);
  }, [reactFlowInstance]);

  const value = {
    addNodeFromComponent,
  };

  return (
    <FlowContext.Provider value={value}>
      {children}
    </FlowContext.Provider>
  );
} 