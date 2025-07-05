import { useNodeContext } from '@/contexts/node-context';
import { api } from '@/services/api';
import { useCallback, useEffect, useRef, useState } from 'react';

// Connection state for a specific flow
export type FlowConnectionState = 'idle' | 'connecting' | 'connected' | 'error' | 'completed';

interface FlowConnectionInfo {
  state: FlowConnectionState;
  abortController: (() => void) | null;
  startTime: number;
  lastActivity: number;
  error?: string;
}

// Global connection manager - tracks all active flow connections
class FlowConnectionManager {
  private connections = new Map<string, FlowConnectionInfo>();
  private listeners = new Set<() => void>();

  // Get connection info for a flow
  getConnection(flowId: string): FlowConnectionInfo {
    return this.connections.get(flowId) || {
      state: 'idle',
      abortController: null,
      startTime: 0,
      lastActivity: 0,
    };
  }

  // Set connection info for a flow
  setConnection(flowId: string, info: Partial<FlowConnectionInfo>): void {
    const existing = this.getConnection(flowId);
    const updated = {
      ...existing,
      ...info,
      lastActivity: Date.now(),
    };
    
    this.connections.set(flowId, updated);
    this.notifyListeners();
  }

  // Remove connection for a flow
  removeConnection(flowId: string): void {
    const connection = this.connections.get(flowId);
    if (connection?.abortController) {
      connection.abortController();
    }
    this.connections.delete(flowId);
    this.notifyListeners();
  }

  // Get all active connections
  getActiveConnections(): Map<string, FlowConnectionInfo> {
    return new Map(this.connections);
  }

  // Check if any flow is processing
  hasActiveConnections(): boolean {
    return Array.from(this.connections.values()).some(
      conn => conn.state === 'connecting' || conn.state === 'connected'
    );
  }

  // Add listener for connection changes
  addListener(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notifyListeners(): void {
    this.listeners.forEach(listener => listener());
  }

  // Cleanup stale connections (older than 5 minutes with no activity)
  cleanupStaleConnections(): void {
    const now = Date.now();
    const staleThreshold = 5 * 60 * 1000; // 5 minutes

    for (const [flowId, connection] of this.connections.entries()) {
      if (now - connection.lastActivity > staleThreshold && 
          (connection.state === 'connecting' || connection.state === 'connected')) {
        console.warn(`Cleaning up stale connection for flow ${flowId}`);
        this.removeConnection(flowId);
      }
    }
  }
}

// Global instance
const flowConnectionManager = new FlowConnectionManager();

// Cleanup stale connections every minute
setInterval(() => {
  flowConnectionManager.cleanupStaleConnections();
}, 60000);

// Hook for managing flow connections
export function useFlowConnection(flowId: string | null) {
  const nodeContext = useNodeContext();
  const [, forceUpdate] = useState({});
  const mountedRef = useRef(true);

  // Get current connection info
  const connectionInfo = flowId ? flowConnectionManager.getConnection(flowId) : {
    state: 'idle' as FlowConnectionState,
    abortController: null,
    startTime: 0,
    lastActivity: 0,
  };

  // Listen for connection changes
  useEffect(() => {
    if (!flowId) return;

    const unsubscribe = flowConnectionManager.addListener(() => {
      if (mountedRef.current) {
        forceUpdate({});
      }
    });

    return unsubscribe;
  }, [flowId]);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Get agent states for current flow to derive processing status
  const agentNodeData = nodeContext.getAgentNodeDataForFlow(flowId);
  const isProcessing = Object.values(agentNodeData).some(
    agent => agent.status === 'IN_PROGRESS'
  );

  // Derived state
  const isConnected = connectionInfo.state === 'connected';
  const isConnecting = connectionInfo.state === 'connecting';
  const hasError = connectionInfo.state === 'error';
  const canRun = !isConnecting && !isConnected && flowId !== null;

  // Start a flow connection
  const runFlow = useCallback((
    params: {
      tickers: string[];
      selected_agents: string[];
      agent_models?: any[];
      start_date?: string;
      end_date?: string;
      model_name?: string;
      model_provider?: any;
    }
  ) => {
    if (!flowId || !canRun) return;

    // Reset node states for this flow
    nodeContext.resetAllNodes(flowId);

    // Set connecting state
    flowConnectionManager.setConnection(flowId, {
      state: 'connecting',
      startTime: Date.now(),
    });

    try {
      // Start the API call
      const abortController = api.runHedgeFund(params, nodeContext, flowId);

      // Update connection with abort controller
      flowConnectionManager.setConnection(flowId, {
        state: 'connected',
        abortController,
      });

      // TODO: We should enhance the API to notify us when the connection completes
      // For now, we'll rely on the complete event from the SSE stream
      
    } catch (error) {
      console.error('Failed to start flow:', error);
      flowConnectionManager.setConnection(flowId, {
        state: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
        abortController: null,
      });
    }
  }, [flowId, canRun, nodeContext]);

  // Stop a flow connection
  const stopFlow = useCallback(() => {
    if (!flowId) return;

    const connection = flowConnectionManager.getConnection(flowId);
    if (connection.abortController) {
      connection.abortController();
    }

    // Update connection state
    flowConnectionManager.setConnection(flowId, {
      state: 'idle',
      abortController: null,
    });
  }, [flowId, nodeContext]);

  // Recover from stale states (called when loading a flow)
  const recoverFlowState = useCallback(() => {
    if (!flowId) return;

    const agentData = nodeContext.getAgentNodeDataForFlow(flowId);
    const connection = flowConnectionManager.getConnection(flowId);

    // If we have IN_PROGRESS states but no active connection, reset them
    const hasInProgressNodes = Object.values(agentData).some(
      agent => agent.status === 'IN_PROGRESS'
    );

    if (hasInProgressNodes && connection.state === 'idle') {      
      // Reset IN_PROGRESS nodes to IDLE, keep final states
      Object.entries(agentData).forEach(([nodeId, data]) => {
        if (data.status === 'IN_PROGRESS') {
          nodeContext.updateAgentNode(flowId, nodeId, {
            ...data,
            status: 'IDLE',
          });
        }
      });
    }
  }, [flowId, nodeContext]);

  // Handle flow completion (should be called by SSE complete event)
  const handleFlowComplete = useCallback(() => {
    if (!flowId) return;

    flowConnectionManager.setConnection(flowId, {
      state: 'completed',
      abortController: null,
    });

    // Optional: Auto-cleanup completed connections after a delay
    setTimeout(() => {
      if (flowConnectionManager.getConnection(flowId).state === 'completed') {
        flowConnectionManager.setConnection(flowId, {
          state: 'idle',
        });
      }
    }, 30000); // 30 seconds
  }, [flowId]);

  // Handle flow error (should be called by SSE error event)
  const handleFlowError = useCallback((error: string) => {
    if (!flowId) return;

    flowConnectionManager.setConnection(flowId, {
      state: 'error',
      error,
      abortController: null,
    });

    // Auto-reset error state after a delay
    setTimeout(() => {
      if (flowConnectionManager.getConnection(flowId).state === 'error') {
        flowConnectionManager.setConnection(flowId, {
          state: 'idle',
          error: undefined,
        });
      }
    }, 10000); // 10 seconds
  }, [flowId]);

  return {
    // Connection state
    connectionState: connectionInfo.state,
    isConnected,
    isConnecting,
    isProcessing,
    hasError,
    error: connectionInfo.error,
    canRun,
    startTime: connectionInfo.startTime,
    lastActivity: connectionInfo.lastActivity,

    // Actions
    runFlow,
    stopFlow,
    recoverFlowState,
    handleFlowComplete,
    handleFlowError,

    // Global state
    hasActiveConnections: flowConnectionManager.hasActiveConnections(),
    activeConnections: flowConnectionManager.getActiveConnections(),
  };
}

// Utility hook to get connection state for any flow (for monitoring)
export function useFlowConnectionState(flowId: string | null) {
  const [, forceUpdate] = useState({});

  useEffect(() => {
    if (!flowId) return;

    const unsubscribe = flowConnectionManager.addListener(() => {
      forceUpdate({});
    });

    return unsubscribe;
  }, [flowId]);

  return flowId ? flowConnectionManager.getConnection(flowId) : null;
}

// Export manager for advanced use cases
export { flowConnectionManager };
