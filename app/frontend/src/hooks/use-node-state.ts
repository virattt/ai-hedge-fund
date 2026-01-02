import { useCallback, useEffect, useState } from 'react';

// =============================================================================
// FLOW STATE MANAGER - Handles global state and flow isolation
// =============================================================================

class FlowStateManager {
  private nodeStatesMap = new Map<string, Record<string, any>>();
  private stateChangeListeners = new Set<() => void>();
  private flowIdChangeListeners = new Set<() => void>();
  private currentFlowId: string | null = null;

  // Flow ID Management
  setCurrentFlowId(flowId: string | null): void {
    const oldFlowId = this.currentFlowId;
    this.currentFlowId = flowId;
    
    if (oldFlowId !== flowId) {
      this.notifyFlowIdChange();
    }
  }

  getCurrentFlowId(): string | null {
    return this.currentFlowId;
  }

  // Key Generation
  private createCompositeKey(nodeId: string): string {
    return this.currentFlowId ? `${this.currentFlowId}:${nodeId}` : nodeId;
  }

  // State Access
  getNodeState(nodeId: string, stateKey: string): any {
    const compositeKey = this.createCompositeKey(nodeId);
    const nodeState = this.nodeStatesMap.get(compositeKey);
    return nodeState?.[stateKey];
  }

  setNodeState(nodeId: string, stateKey: string, value: any): void {
    const compositeKey = this.createCompositeKey(nodeId);
    
    if (!this.nodeStatesMap.has(compositeKey)) {
      this.nodeStatesMap.set(compositeKey, {});
    }
    
    this.nodeStatesMap.get(compositeKey)![stateKey] = value;
    this.notifyStateChange();
  }

  // Node Management
  getNodeInternalState(nodeId: string): Record<string, any> | undefined {
    const compositeKey = this.createCompositeKey(nodeId);
    return this.nodeStatesMap.get(compositeKey);
  }

  setNodeInternalState(nodeId: string, state: Record<string, any>): void {
    const compositeKey = this.createCompositeKey(nodeId);
    this.nodeStatesMap.set(compositeKey, { ...state });
    this.notifyStateChange();
  }

  clearNodeInternalState(nodeId: string): void {
    const compositeKey = this.createCompositeKey(nodeId);
    this.nodeStatesMap.delete(compositeKey);
    this.notifyStateChange();
  }

  // Flow Management
  getAllNodeStates(): Map<string, Record<string, any>> {
    if (!this.currentFlowId) {
      // Backward compatibility - return all states
      return new Map(this.nodeStatesMap);
    }
    
    // Filter states for current flow and strip flow prefix
    const currentFlowStates = new Map<string, Record<string, any>>();
    const flowPrefix = `${this.currentFlowId}:`;
    
    for (const [compositeKey, state] of this.nodeStatesMap.entries()) {
      if (compositeKey.startsWith(flowPrefix)) {
        const nodeId = compositeKey.substring(flowPrefix.length);
        currentFlowStates.set(nodeId, state);
      }
    }
    
    return currentFlowStates;
  }

  clearAllNodeStates(): void {
    if (!this.currentFlowId) {
      // Backward compatibility - clear all states
      this.nodeStatesMap.clear();
    } else {
      // Clear only current flow's states
      const flowPrefix = `${this.currentFlowId}:`;
      const keysToDelete = Array.from(this.nodeStatesMap.keys())
        .filter(key => key.startsWith(flowPrefix));
      
      keysToDelete.forEach(key => this.nodeStatesMap.delete(key));
    }
    
    this.notifyStateChange();
  }

  clearFlowNodeStates(flowId: string): void {
    const flowPrefix = `${flowId}:`;
    const keysToDelete = Array.from(this.nodeStatesMap.keys())
      .filter(key => key.startsWith(flowPrefix));
    
    keysToDelete.forEach(key => this.nodeStatesMap.delete(key));
    this.notifyStateChange();
  }

  // Listener Management
  addStateChangeListener(listener: () => void): () => void {
    this.stateChangeListeners.add(listener);
    return () => this.stateChangeListeners.delete(listener);
  }

  addFlowIdChangeListener(listener: () => void): () => void {
    this.flowIdChangeListeners.add(listener);
    return () => this.flowIdChangeListeners.delete(listener);
  }

  private notifyStateChange(): void {
    this.stateChangeListeners.forEach(listener => listener());
  }

  private notifyFlowIdChange(): void {
    this.flowIdChangeListeners.forEach(listener => listener());
  }
}

// Global instance
const flowStateManager = new FlowStateManager();

// =============================================================================
// PUBLIC API - Clean interface for external use
// =============================================================================

export interface UseNodeStateReturn<T> {
  0: T;
  1: (value: T | ((prev: T) => T)) => void;
}

// Flow Management
export function setCurrentFlowId(flowId: string | null): void {
  flowStateManager.setCurrentFlowId(flowId);
}

// Node State Management
export function getNodeInternalState(nodeId: string): Record<string, any> | undefined {
  return flowStateManager.getNodeInternalState(nodeId);
}

export function setNodeInternalState(nodeId: string, state: Record<string, any>): void {
  flowStateManager.setNodeInternalState(nodeId, state);
}

export function clearNodeInternalState(nodeId: string): void {
  flowStateManager.clearNodeInternalState(nodeId);
}

// Flow State Management
export function getAllNodeStates(): Map<string, Record<string, any>> {
  return flowStateManager.getAllNodeStates();
}

export function clearAllNodeStates(): void {
  flowStateManager.clearAllNodeStates();
}

export function clearFlowNodeStates(flowId: string): void {
  flowStateManager.clearFlowNodeStates(flowId);
}

export function addStateChangeListener(listener: () => void): () => void {
  return flowStateManager.addStateChangeListener(listener);
}

// =============================================================================
// REACT HOOKS - Focused on React integration
// =============================================================================

/**
 * Drop-in replacement for useState that automatically persists state across
 * flow saves/loads and provides flow isolation.
 * 
 * @param nodeId - The ID of the node (from NodeProps)
 * @param stateKey - Unique key for this state value within the node  
 * @param defaultValue - Default value for the state
 * @returns [value, setValue] tuple like useState
 */
export function useNodeState<T>(
  nodeId: string,
  stateKey: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  
  // Initialize with stored value or default
  const getStoredValue = useCallback((): T => {
    const storedValue = flowStateManager.getNodeState(nodeId, stateKey);
    return storedValue !== undefined ? storedValue : defaultValue;
  }, [nodeId, stateKey, defaultValue]);

  const [value, setValue] = useState<T>(getStoredValue);
  const [, forceUpdate] = useState({});

  // Handle flow changes - reset to stored value for new flow
  useEffect(() => {
    const unsubscribe = flowStateManager.addFlowIdChangeListener(() => {
      // Use setTimeout to defer the state update to avoid updating during render
      setTimeout(() => {
        const newValue = getStoredValue();
        setValue(newValue);
        forceUpdate({}); // Force re-render
      }, 0);
    });
    
    return unsubscribe;
  }, [getStoredValue]);

  // Handle external state changes - update if this specific state changed
  useEffect(() => {
    const unsubscribe = flowStateManager.addStateChangeListener(() => {
      const storedValue = flowStateManager.getNodeState(nodeId, stateKey);
      if (storedValue !== undefined) {
        // Use setTimeout to defer the state update to avoid updating during render
        setTimeout(() => {
          setValue(prevValue => {
            if (prevValue !== storedValue) {
              console.debug(`[useNodeState] Updated ${nodeId}.${stateKey}:`, storedValue);
              return storedValue;
            }
            return prevValue;
          });
        }, 0);
      }
    });
    
    return unsubscribe;
  }, [nodeId, stateKey]);

  // Persist value when it changes
  const setValueAndPersist = useCallback((newValue: T | ((prev: T) => T)) => {
    setValue(prevValue => {
      const finalValue = typeof newValue === 'function' 
        ? (newValue as (prev: T) => T)(prevValue) 
        : newValue;
      
      flowStateManager.setNodeState(nodeId, stateKey, finalValue);
      return finalValue;
    });
  }, [nodeId, stateKey]);

  // Initialize stored state on mount or flow change
  useEffect(() => {
    const storedValue = flowStateManager.getNodeState(nodeId, stateKey);
    if (storedValue === undefined) {
      // Use setTimeout to defer the state update to avoid updating during render
      setTimeout(() => {
        flowStateManager.setNodeState(nodeId, stateKey, value);
      }, 0);
    }
  }, [nodeId, stateKey, value]);

  return [value, setValueAndPersist];
}