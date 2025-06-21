import { LanguageModel } from '@/data/models';
import { createContext, ReactNode, useCallback, useContext, useState } from 'react';

export type NodeStatus = 'IDLE' | 'IN_PROGRESS' | 'COMPLETE' | 'ERROR';

// Message history item
export interface MessageItem {
  timestamp: string;
  message: string;
  ticker: string | null;
  analysis: Record<string, string>;
}

// Agent node state structure
export interface AgentNodeData {
  status: NodeStatus;
  ticker: string | null;
  message: string;
  lastUpdated: number;
  messages: MessageItem[];
  timestamp?: string;
  analysis: string | null;
}

// Data structure for the output node data (from complete event)
export interface OutputNodeData {
  decisions: Record<string, any>;
  analyst_signals: Record<string, any>;
}

// Default agent node state
const DEFAULT_AGENT_NODE_STATE: AgentNodeData = {
  status: 'IDLE',
  ticker: null,
  message: '',
  messages: [],
  lastUpdated: Date.now(),
  analysis: null,
};

interface NodeContextType {
  agentNodeData: Record<string, AgentNodeData>;
  outputNodeData: OutputNodeData | null;
  agentModels: Record<string, LanguageModel | null>;
  updateAgentNode: (nodeId: string, data: Partial<AgentNodeData> | NodeStatus) => void;
  updateAgentNodes: (nodeIds: string[], status: NodeStatus) => void;
  setOutputNodeData: (data: OutputNodeData) => void;
  setAgentModel: (nodeId: string, model: LanguageModel | null) => void;
  getAgentModel: (nodeId: string) => LanguageModel | null;
  getAllAgentModels: () => Record<string, LanguageModel | null>;
  resetAllNodes: () => void;
}

const NodeContext = createContext<NodeContextType | undefined>(undefined);

export function NodeProvider({ children }: { children: ReactNode }) {
  const [agentNodeData, setAgentNodeData] = useState<Record<string, AgentNodeData>>({});
  const [outputNodeData, setOutputNodeData] = useState<OutputNodeData | null>(null);
  const [agentModels, setAgentModels] = useState<Record<string, LanguageModel | null>>({});

  const updateAgentNode = useCallback((nodeId: string, data: Partial<AgentNodeData> | NodeStatus) => {
    // Handle string status shorthand (just passing a status string)
    if (typeof data === 'string') {
      setAgentNodeData(prev => {
        const existingNode = prev[nodeId] || { ...DEFAULT_AGENT_NODE_STATE };
        return {
          ...prev,
          [nodeId]: {
            ...existingNode,
            status: data,
            lastUpdated: Date.now()
          }
        };
      });
      return;
    }

    // Handle data object - full update
    setAgentNodeData(prev => {
      const existingNode = prev[nodeId] || { ...DEFAULT_AGENT_NODE_STATE };
      const newMessages = [...existingNode.messages];
      
      // Add message to history if it's new based on timestamp
      if (data.message && data.timestamp !== existingNode.timestamp) {
        // Get the reasoning for the current ticker if available
        const ticker = data.ticker || null;

        const messageItem: MessageItem = {
          timestamp: data.timestamp || new Date().toISOString(),
          message: data.message,
          ticker: ticker,
          analysis: {} as Record<string, string>,
        }

        // Add analysis for ticker to messageItem if ticker is not null
        if (ticker && data.analysis) {
          messageItem.analysis[ticker] = data.analysis;
        }

        newMessages.push(messageItem);
      }
      
      return {
        ...prev,
        [nodeId]: {
          ...existingNode,
          ...data,
          messages: newMessages,
          lastUpdated: Date.now()
        }
      };
    });
  }, []);

  const updateAgentNodes = useCallback((nodeIds: string[], status: NodeStatus) => {
    if (nodeIds.length === 0) return;
    
    setAgentNodeData(prev => {
      const newStates = { ...prev };
      
      nodeIds.forEach(id => {
        newStates[id] = {
          ...(newStates[id] || { ...DEFAULT_AGENT_NODE_STATE }),
          status,
          lastUpdated: Date.now()
        };
      });
      
      return newStates;
    });
  }, []);

  const setAgentModel = useCallback((nodeId: string, model: LanguageModel | null) => {
    setAgentModels(prev => {
      if (model === null) {
        // Remove the agent model if setting to null
        const { [nodeId]: removed, ...rest } = prev;
        return rest;
      } else {
        // Set the agent model
        return {
          ...prev,
          [nodeId]: model
        };
      }
    });
  }, []);

  const getAgentModel = useCallback((nodeId: string): LanguageModel | null => {
    return agentModels[nodeId] || null;
  }, [agentModels]);

  const getAllAgentModels = useCallback((): Record<string, LanguageModel | null> => {
    return agentModels;
  }, [agentModels]);

  const resetAllNodes = useCallback(() => {
    setAgentNodeData({});
    setOutputNodeData(null);
    // Note: We don't reset agentModels here as users would want to keep their model selections
  }, []);

  return (
    <NodeContext.Provider
      value={{
        agentNodeData,
        outputNodeData,
        agentModels,
        updateAgentNode,
        updateAgentNodes,
        setOutputNodeData,
        setAgentModel,
        getAgentModel,
        getAllAgentModels,
        resetAllNodes,
      }}
    >
      {children}
    </NodeContext.Provider>
  );
}

export function useNodeContext() {
  const context = useContext(NodeContext);
  
  if (context === undefined) {
    throw new Error('useNodeContext must be used within a NodeProvider');
  }
  
  return context;
} 