import { useNodeContext } from '@/contexts/node-context';
import { api } from '@/services/api';
import { backtestApi } from '@/services/backtest-api';
import { BacktestRequest, HedgeFundRequest } from '@/services/types';
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

  // Add listener for connection changes
  addListener(listener: () => void): void {
    this.listeners.add(listener);
  }

  // Remove listener
  removeListener(listener: () => void): void {
    this.listeners.delete(listener);
  }

  // Notify all listeners of changes
  private notifyListeners(): void {
    this.listeners.forEach(listener => listener());
  }
}

// Global instance
export const flowConnectionManager = new FlowConnectionManager();

/**
 * Hook for managing flow connections and execution
 * @param flowId The ID of the flow to manage
 * @returns Connection state and control functions
 */
export function useFlowConnection(flowId: string | null) {
  const nodeContext = useNodeContext();
  const [, forceUpdate] = useState({});
  const listenerRef = useRef<() => void>();

  // Force re-render when connections change
  useEffect(() => {
    const listener = () => forceUpdate({});
    listenerRef.current = listener;
    flowConnectionManager.addListener(listener);
    
    return () => {
      if (listenerRef.current) {
        flowConnectionManager.removeListener(listenerRef.current);
      }
    };
  }, []);

  // Get current connection state
  const connection = flowId ? flowConnectionManager.getConnection(flowId) : null;
  const isConnecting = connection?.state === 'connecting';
  const isConnected = connection?.state === 'connected';
  const isError = connection?.state === 'error';
  const isCompleted = connection?.state === 'completed';
  
  // Check if any agents are currently processing
  const isProcessing = flowId ? (() => {
    const agentData = nodeContext.getAgentNodeDataForFlow(flowId);
    return Object.values(agentData).some(agent => agent.status === 'IN_PROGRESS');
  })() : false;
  
  // Can run if we have a flow ID and we're not already running
  const canRun = Boolean(flowId && !isConnecting && !isConnected && !isProcessing);

  // Start a flow connection
  const runFlow = useCallback((params: HedgeFundRequest) => {
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
      console.error('Failed to start hedge fund run:', error);
      flowConnectionManager.setConnection(flowId, {
        state: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
        abortController: null,
      });
    }
  }, [flowId, canRun, nodeContext]);

  // Start a backtest connection
  const runBacktest = useCallback((params: BacktestRequest) => {
    if (!flowId || !canRun) return;

    // Reset node states for this flow
    nodeContext.resetAllNodes(flowId);

    // Set connecting state
    flowConnectionManager.setConnection(flowId, {
      state: 'connecting',
      startTime: Date.now(),
    });

    try {
      // Start the backtest API call
      const abortController = backtestApi.runBacktest(params, nodeContext, flowId);

      // Update connection with abort controller
      flowConnectionManager.setConnection(flowId, {
        state: 'connected',
        abortController,
      });

      // TODO: We should enhance the API to notify us when the connection completes
      // For now, we'll rely on the complete event from the SSE stream
      
    } catch (error) {
      console.error('Failed to start backtest:', error);
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

    console.log(`[stopFlow] Stopping flow ${flowId}`);
    const connection = flowConnectionManager.getConnection(flowId);
    console.log(`[stopFlow] Current connection state:`, connection);
    
    if (connection.abortController) {
      console.log(`[stopFlow] Calling abort controller for flow ${flowId}`);
      connection.abortController();
    } else {
      console.log(`[stopFlow] No abort controller found for flow ${flowId}`);
    }

    // Reset only node statuses when stopping, preserving all data (backtest results, messages, etc.)
    nodeContext.resetNodeStatuses(flowId);

    // Update connection state
    flowConnectionManager.setConnection(flowId, {
      state: 'idle',
      abortController: null,
    });
    
    console.log(`[stopFlow] Flow ${flowId} stopped and reset to idle`);
  }, [flowId, nodeContext]);

  // Recover from stale states (called when loading a flow)
  const recoverFlowState = useCallback(() => {
    if (!flowId) return;

    const connection = flowConnectionManager.getConnection(flowId);
    
    // If we think we're connected but have no processing nodes, we're probably stale
    if ((connection.state === 'connected' || connection.state === 'connecting') && !isProcessing) {
      // Check if the connection is old (more than 5 minutes)
      const isStale = Date.now() - connection.lastActivity > 5 * 60 * 1000;
      
      if (isStale) {
        console.log(`Recovering stale connection for flow ${flowId}`);
        flowConnectionManager.setConnection(flowId, {
          state: 'idle',
          abortController: null,
        });
      }
    }
  }, [flowId, isProcessing]);

  return {
    // State
    isConnecting,
    isConnected,
    isError,
    isCompleted,
    isProcessing,
    canRun,
    error: connection?.error,
    
    // Actions
    runFlow,
    runBacktest,
    stopFlow,
    recoverFlowState,
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
