import { createContext, ReactNode, useCallback, useContext, useState } from 'react';

export type NodeStatus = 'IDLE' | 'IN_PROGRESS' | 'COMPLETE' | 'ERROR';

interface NodeState {
  [nodeId: string]: NodeStatus;
}

interface NodeStatusContextType {
  nodeStates: NodeState;
  updateNodeStatus: (nodeId: string, status: NodeStatus) => void;
  updateNodesStatus: (nodeIds: string[], status: NodeStatus) => void;
  resetAllStatuses: () => void;
}

const NodeStatusContext = createContext<NodeStatusContextType | undefined>(undefined);

export function NodeStatusProvider({ children }: { children: ReactNode }) {
  const [nodeStates, setNodeStates] = useState<NodeState>({});

  const updateNodeStatus = useCallback((nodeId: string, status: NodeStatus) => {
    setNodeStates((prevStates) => ({
      ...prevStates,
      [nodeId]: status,
    }));
  }, []);

  const updateNodesStatus = useCallback((nodeIds: string[], status: NodeStatus) => {
    setNodeStates((prevStates) => {
      const newStates = { ...prevStates };
      nodeIds.forEach((id) => {
        newStates[id] = status;
      });
      return newStates;
    });
  }, []);

  const resetAllStatuses = useCallback(() => {
    setNodeStates({});
  }, []);

  return (
    <NodeStatusContext.Provider
      value={{
        nodeStates,
        updateNodeStatus,
        updateNodesStatus,
        resetAllStatuses,
      }}
    >
      {children}
    </NodeStatusContext.Provider>
  );
}

export function useNodeStatus() {
  const context = useContext(NodeStatusContext);
  
  if (context === undefined) {
    throw new Error('useNodeStatus must be used within a NodeStatusProvider');
  }
  
  return context;
} 