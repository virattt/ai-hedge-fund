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

// Helper function to create flow-aware composite keys
function createCompositeKey(flowId: string | null, nodeId: string): string {
  return flowId ? `${flowId}:${nodeId}` : nodeId;
}

interface NodeContextType {
  agentNodeData: Record<string, AgentNodeData>;
  outputNodeData: OutputNodeData | null;
  agentModels: Record<string, LanguageModel | null>;
  updateAgentNode: (flowId: string | null, nodeId: string, data: Partial<AgentNodeData> | NodeStatus) => void;
  updateAgentNodes: (flowId: string | null, nodeIds: string[], status: NodeStatus) => void;
  setOutputNodeData: (flowId: string | null, data: OutputNodeData) => void;
  setAgentModel: (flowId: string | null, nodeId: string, model: LanguageModel | null) => void;
  getAgentModel: (flowId: string | null, nodeId: string) => LanguageModel | null;
  getAllAgentModels: (flowId: string | null) => Record<string, LanguageModel | null>;
  resetAllNodes: (flowId: string | null) => void;
  exportNodeContextData: (flowId: string | null) => {
    agentNodeData: Record<string, AgentNodeData>;
    outputNodeData: OutputNodeData | null;
  };
  importNodeContextData: (flowId: string | null, data: {
    agentNodeData?: Record<string, AgentNodeData>;
    outputNodeData?: OutputNodeData | null;
  }) => void;
  // New flow-aware functions
  getAgentNodeDataForFlow: (flowId: string | null) => Record<string, AgentNodeData>;
  getOutputNodeDataForFlow: (flowId: string | null) => OutputNodeData | null;
}

const NodeContext = createContext<NodeContextType | undefined>(undefined);

export function NodeProvider({ children }: { children: ReactNode }) {
  // Use composite keys for flow-aware agent node data storage
  const [agentNodeData, setAgentNodeData] = useState<Record<string, AgentNodeData>>({});
  // Flow-aware output node data storage
  const [outputNodeData, setOutputNodeData] = useState<Record<string, OutputNodeData>>({});
  // Agent models also need to be flow-aware to maintain model selections per flow
  const [agentModels, setAgentModels] = useState<Record<string, LanguageModel | null>>({});

  const updateAgentNode = useCallback((flowId: string | null, nodeId: string, data: Partial<AgentNodeData> | NodeStatus) => {
    const compositeKey = createCompositeKey(flowId, nodeId);
    
    // Handle string status shorthand (just passing a status string)
    if (typeof data === 'string') {
      setAgentNodeData(prev => {
        const existingNode = prev[compositeKey] || { ...DEFAULT_AGENT_NODE_STATE };
        return {
          ...prev,
          [compositeKey]: {
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
      const existingNode = prev[compositeKey] || { ...DEFAULT_AGENT_NODE_STATE };
      const newMessages = [...existingNode.messages];
      
      // Add message to history if it's new - use more robust checking
      if (data.message && data.timestamp) {
        // Check if this exact message already exists (prevent duplicates)
        const messageExists = newMessages.some(msg => 
          msg.timestamp === data.timestamp && 
          msg.message === data.message &&
          msg.ticker === data.ticker
        );
        
        if (!messageExists) {
          const ticker = data.ticker || null;

          const messageItem: MessageItem = {
            timestamp: data.timestamp,
            message: data.message,
            ticker: ticker,
            analysis: {} as Record<string, string>,
          }

          // Add analysis for ticker to messageItem if ticker is not null
          if (ticker && data.analysis) {
            messageItem.analysis[ticker] = data.analysis;
          }

          newMessages.push(messageItem);
          
          // Debug logging for background processing
          if (flowId) {
            console.debug(`[NodeContext] Added message for ${flowId}:${nodeId} - ${ticker || 'no ticker'}: ${data.message} (total: ${newMessages.length})`);
          }
        } else {
          console.debug(`[NodeContext] Duplicate message detected for ${flowId}:${nodeId} - ${data.ticker || 'no ticker'}: ${data.message}`);
        }
      }
      
      const updatedNode = {
        ...existingNode,
        ...data,
        messages: newMessages,
        lastUpdated: Date.now()
      };
      
      // Debug logging for state updates
      if (flowId && data.status) {
        console.debug(`[NodeContext] Updated ${flowId}:${nodeId} status: ${data.status} (${newMessages.length} messages)`);
      }
      
      return {
        ...prev,
        [compositeKey]: updatedNode
      };
    });
  }, []);

  const updateAgentNodes = useCallback((flowId: string | null, nodeIds: string[], status: NodeStatus) => {
    if (nodeIds.length === 0) return;
    
    setAgentNodeData(prev => {
      const newStates = { ...prev };
      
      nodeIds.forEach(id => {
        const compositeKey = createCompositeKey(flowId, id);
        newStates[compositeKey] = {
          ...(newStates[compositeKey] || { ...DEFAULT_AGENT_NODE_STATE }),
          status,
          lastUpdated: Date.now()
        };
      });
      
      return newStates;
    });
  }, []);

  const setAgentModel = useCallback((flowId: string | null, nodeId: string, model: LanguageModel | null) => {
    const compositeKey = createCompositeKey(flowId, nodeId);
    
    setAgentModels(prev => {
      if (model === null) {
        // Remove the agent model if setting to null
        const { [compositeKey]: removed, ...rest } = prev;
        return rest;
      } else {
        // Set the agent model
        return {
          ...prev,
          [compositeKey]: model
        };
      }
    });
  }, []);

  const getAgentModel = useCallback((flowId: string | null, nodeId: string): LanguageModel | null => {
    const compositeKey = createCompositeKey(flowId, nodeId);
    return agentModels[compositeKey] || null;
  }, [agentModels]);

  const getAllAgentModels = useCallback((flowId: string | null): Record<string, LanguageModel | null> => {
    // Return only models for the specified flow
    if (!flowId) {
      // If no flow ID, return models without flow prefix (backward compatibility)
      return Object.fromEntries(
        Object.entries(agentModels).filter(([key]) => !key.includes(':'))
      );
    }
    
    const flowPrefix = `${flowId}:`;
    const currentFlowModels: Record<string, LanguageModel | null> = {};
    
    Object.entries(agentModels).forEach(([compositeKey, model]) => {
      if (compositeKey.startsWith(flowPrefix)) {
        const nodeId = compositeKey.substring(flowPrefix.length);
        currentFlowModels[nodeId] = model;
      }
    });
    
    return currentFlowModels;
  }, [agentModels]);

  const setOutputNodeDataForFlow = useCallback((flowId: string | null, data: OutputNodeData) => {
    if (!flowId) {
      // If no flow ID, use 'default' as key for backward compatibility
      setOutputNodeData(prev => ({ ...prev, 'default': data }));
    } else {
      setOutputNodeData(prev => ({ ...prev, [flowId]: data }));
    }
  }, []);

  const resetAllNodes = useCallback((flowId: string | null) => {
    // Clear all agent data for specified flow only
    if (!flowId) {
      // If no flow ID, clear all data (backward compatibility)
      setAgentNodeData({});
      setOutputNodeData({});
    } else {
      // Clear only data for specified flow
      const flowPrefix = `${flowId}:`;
      setAgentNodeData(prev => {
        const newData: Record<string, AgentNodeData> = {};
        Object.entries(prev).forEach(([key, value]) => {
          if (!key.startsWith(flowPrefix)) {
            newData[key] = value;
          }
        });
        return newData;
      });
      
      // Clear output data for specified flow
      setOutputNodeData(prev => {
        const { [flowId]: removed, ...rest } = prev;
        return rest;
      });
    }
    
    // Note: We don't reset agentModels here as users would want to keep their model selections
  }, []);

  // Export node context data for persistence
  const exportNodeContextData = useCallback((flowId: string | null) => {
    // Export agent data for specified flow
    const currentFlowAgentData: Record<string, AgentNodeData> = {};
    const flowPrefix = flowId ? `${flowId}:` : '';
    
    Object.entries(agentNodeData).forEach(([compositeKey, data]) => {
      if (flowId) {
        if (compositeKey.startsWith(flowPrefix)) {
          const nodeId = compositeKey.substring(flowPrefix.length);
          currentFlowAgentData[nodeId] = data;
        }
      } else {
        // If no flow ID, export data without flow prefix (backward compatibility)
        if (!compositeKey.includes(':')) {
          currentFlowAgentData[compositeKey] = data;
        }
      }
    });

    // Export output data for specified flow
    const currentFlowOutputData = flowId 
      ? outputNodeData[flowId] || null
      : outputNodeData['default'] || null;

    return {
      agentNodeData: currentFlowAgentData,
      outputNodeData: currentFlowOutputData,
    };
  }, [agentNodeData, outputNodeData]);

  // Import node context data from persistence
  const importNodeContextData = useCallback((flowId: string | null, data: {
    agentNodeData?: Record<string, AgentNodeData>;
    outputNodeData?: OutputNodeData | null;
  }) => {
    // Import agent data
    if (data.agentNodeData) {
      Object.entries(data.agentNodeData).forEach(([nodeId, nodeData]) => {
        const compositeKey = createCompositeKey(flowId, nodeId);
        setAgentNodeData(prev => ({
          ...prev,
          [compositeKey]: nodeData,
        }));
      });
    }

    // Import output data
    if (data.outputNodeData) {
      if (flowId) {
        setOutputNodeData(prev => ({
          ...prev,
          [flowId]: data.outputNodeData!,
        }));
      } else {
        setOutputNodeData(prev => ({
          ...prev,
          'default': data.outputNodeData!,
        }));
      }
    }
  }, []);

  // Helper functions to get data for a specific flow
  const getAgentNodeDataForFlow = useCallback((flowId: string | null): Record<string, AgentNodeData> => {
    if (!flowId) {
      // If no flow ID, return data without flow prefix (backward compatibility)
      return Object.fromEntries(
        Object.entries(agentNodeData).filter(([key]) => !key.includes(':'))
      );
    }
    
    const flowPrefix = `${flowId}:`;
    const currentFlowData: Record<string, AgentNodeData> = {};
    
    Object.entries(agentNodeData).forEach(([compositeKey, data]) => {
      if (compositeKey.startsWith(flowPrefix)) {
        const nodeId = compositeKey.substring(flowPrefix.length);
        currentFlowData[nodeId] = data;
      }
    });
    
    return currentFlowData;
  }, [agentNodeData]);

  const getOutputNodeDataForFlow = useCallback((flowId: string | null): OutputNodeData | null => {
    if (!flowId) {
      // If no flow ID, return 'default' data for backward compatibility
      return outputNodeData['default'] || null;
    }
    
    return outputNodeData[flowId] || null;
  }, [outputNodeData]);

  // Context value object
  const contextValue = {
    // Legacy getters for backward compatibility - these will return empty data
    // Components should use the explicit flow-based functions instead
    agentNodeData: {},
    outputNodeData: null,
    agentModels,
    updateAgentNode,
    updateAgentNodes,
    setOutputNodeData: setOutputNodeDataForFlow,
    setAgentModel,
    getAgentModel,
    getAllAgentModels,
    resetAllNodes,
    exportNodeContextData,
    importNodeContextData,
    // New flow-aware functions
    getAgentNodeDataForFlow,
    getOutputNodeDataForFlow,
  };

  return (
    <NodeContext.Provider value={contextValue}>
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