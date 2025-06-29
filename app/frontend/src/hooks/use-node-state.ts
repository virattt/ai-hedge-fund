import { useCallback, useEffect, useState } from 'react';

// Global state storage for all node internal states
// Structure: { "flowId:nodeId": { stateKey: value } }
const nodeStatesMap = new Map<string, Record<string, any>>();

// Listeners for state changes (used by flow save/load)
const stateChangeListeners = new Set<() => void>();

// Current flow ID for state isolation
let currentFlowId: string | null = null;

// Listeners for flow ID changes
const flowIdChangeListeners = new Set<() => void>();

export interface UseNodeStateReturn<T> {
  0: T;
  1: (value: T | ((prev: T) => T)) => void;
}

/**
 * Set the current flow ID for state isolation
 * This should be called whenever a flow is loaded or created
 */
export function setCurrentFlowId(flowId: string | null): void {
  const oldFlowId = currentFlowId;
  currentFlowId = flowId;
  
  // Notify all useNodeState hooks that the flow ID has changed
  if (oldFlowId !== flowId) {
    flowIdChangeListeners.forEach(listener => listener());
  }
}

/**
 * Get the current flow ID
 */
export function getCurrentFlowId(): string | null {
  return currentFlowId;
}

/**
 * Create a composite key for flow-aware state storage
 */
function createCompositeKey(nodeId: string): string {
  return currentFlowId ? `${currentFlowId}:${nodeId}` : nodeId;
}

/**
 * Custom hook that provides automatic state persistence for node components.
 * Works as a drop-in replacement for useState, but automatically persists
 * the state when flows are saved and restores it when flows are loaded.
 * 
 * @param nodeId - The ID of the node (typically from NodeProps)
 * @param stateKey - Unique key for this state value within the node
 * @param defaultValue - Default value for the state
 * @returns Tuple similar to useState: [value, setValue]
 */
export function useNodeState<T>(
  nodeId: string,
  stateKey: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  
  // Get initial value from stored state or use default
  const getInitialValue = useCallback((): T => {
    const compositeKey = createCompositeKey(nodeId);
    const nodeState = nodeStatesMap.get(compositeKey);
    if (nodeState && stateKey in nodeState) {
      return nodeState[stateKey];
    }
    return defaultValue;
  }, [nodeId, stateKey, defaultValue]);

  const [value, setValue] = useState<T>(getInitialValue);
  const [, forceUpdate] = useState({});

  // Listen for flow ID changes and update state accordingly
  useEffect(() => {
    const handleFlowIdChange = () => {
      const newValue = getInitialValue();
      setValue(newValue);
      // Force a re-render to ensure components see the new value
      forceUpdate({});
    };

    flowIdChangeListeners.add(handleFlowIdChange);
    return () => {
      flowIdChangeListeners.delete(handleFlowIdChange);
    };
  }, [getInitialValue]);

  // Listen for state changes and update local state if this specific node+stateKey changed
  useEffect(() => {
    const handleStateChange = () => {
      const compositeKey = createCompositeKey(nodeId);
      const nodeState = nodeStatesMap.get(compositeKey);
      if (nodeState && stateKey in nodeState) {
        const newValue = nodeState[stateKey];
        // Only update if the value actually changed to avoid unnecessary re-renders
        setValue(prevValue => {
          if (prevValue !== newValue) {
            console.debug(`[useNodeState] Updated ${nodeId}.${stateKey}:`, newValue);
            return newValue;
          }
          return prevValue;
        });
      }
    };

    stateChangeListeners.add(handleStateChange);
    return () => {
      stateChangeListeners.delete(handleStateChange);
    };
  }, [nodeId, stateKey]);

  // Update the global state map when value changes
  const setValueAndPersist = useCallback((newValue: T | ((prev: T) => T)) => {
    setValue(prevValue => {
      const finalValue = typeof newValue === 'function' ? (newValue as (prev: T) => T)(prevValue) : newValue;
      
      // Update global state map with current composite key
      const compositeKey = createCompositeKey(nodeId);
      if (!nodeStatesMap.has(compositeKey)) {
        nodeStatesMap.set(compositeKey, {});
      }
      nodeStatesMap.get(compositeKey)![stateKey] = finalValue;
      
      // Notify listeners of state change
      stateChangeListeners.forEach(listener => listener());
      
      return finalValue;
    });
  }, [nodeId, stateKey]);

  // Initialize the global state map entry when component mounts or flow changes
  useEffect(() => {
    const compositeKey = createCompositeKey(nodeId);
    if (!nodeStatesMap.has(compositeKey)) {
      nodeStatesMap.set(compositeKey, {});
    }
    
    // Set initial value if not already set
    const nodeState = nodeStatesMap.get(compositeKey)!;
    if (!(stateKey in nodeState)) {
      nodeState[stateKey] = value;
    }
  }, [nodeId, stateKey, value, currentFlowId]); // Include currentFlowId as dependency

  return [value, setValueAndPersist];
}

/**
 * Get all internal state for a specific node in the current flow
 */
export function getNodeInternalState(nodeId: string): Record<string, any> | undefined {
  const compositeKey = createCompositeKey(nodeId);
  return nodeStatesMap.get(compositeKey);
}

/**
 * Set internal state for a specific node in the current flow (used during flow loading)
 */
export function setNodeInternalState(nodeId: string, state: Record<string, any>): void {
  const compositeKey = createCompositeKey(nodeId);
  nodeStatesMap.set(compositeKey, { ...state });
  // Notify listeners that state has been updated
  stateChangeListeners.forEach(listener => listener());
}

/**
 * Clear all internal state for a specific node in the current flow (used when node is deleted)
 */
export function clearNodeInternalState(nodeId: string): void {
  const compositeKey = createCompositeKey(nodeId);
  nodeStatesMap.delete(compositeKey);
  stateChangeListeners.forEach(listener => listener());
}

/**
 * Get all node states for the current flow (used for flow saving)
 */
export function getAllNodeStates(): Map<string, Record<string, any>> {
  const currentFlowStates = new Map<string, Record<string, any>>();
  
  if (!currentFlowId) {
    // If no flow ID, return all states (backward compatibility)
    return new Map(nodeStatesMap);
  }
  
  // Filter states for current flow and strip flow prefix from keys
  const flowPrefix = `${currentFlowId}:`;
  for (const [compositeKey, state] of nodeStatesMap.entries()) {
    if (compositeKey.startsWith(flowPrefix)) {
      const nodeId = compositeKey.substring(flowPrefix.length);
      currentFlowStates.set(nodeId, state);
    }
  }
  
  return currentFlowStates;
}

/**
 * Clear all node states for the current flow (used for flow reset)
 */
export function clearAllNodeStates(): void {
  if (!currentFlowId) {
    // If no flow ID, clear all states (backward compatibility)
    nodeStatesMap.clear();
  } else {
    // Clear only states for current flow
    const flowPrefix = `${currentFlowId}:`;
    const keysToDelete = Array.from(nodeStatesMap.keys()).filter(key => 
      key.startsWith(flowPrefix)
    );
    keysToDelete.forEach(key => nodeStatesMap.delete(key));
  }
  
  stateChangeListeners.forEach(listener => listener());
}

/**
 * Clear all node states for a specific flow (used when flow is deleted)
 */
export function clearFlowNodeStates(flowId: string): void {
  const flowPrefix = `${flowId}:`;
  const keysToDelete = Array.from(nodeStatesMap.keys()).filter(key => 
    key.startsWith(flowPrefix)
  );
  keysToDelete.forEach(key => nodeStatesMap.delete(key));
  stateChangeListeners.forEach(listener => listener());
}

/**
 * Add a listener for state changes (used by flow management)
 */
export function addStateChangeListener(listener: () => void): () => void {
  stateChangeListeners.add(listener);
  return () => stateChangeListeners.delete(listener);
}

/**
 * Hook to get the current node ID from React Flow context
 * This is a convenience hook for components that need their node ID
 */
export function useNodeId(): string | null {
  // This would need to be implemented based on how you pass node ID to components
  // For now, we'll return null and expect components to pass nodeId explicitly
  return null;
}

/**
 * Convenience hook that automatically gets the node ID and provides useNodeState
 * Usage: const [value, setValue] = useAutoNodeState('stateKey', defaultValue);
 * Note: This requires the component to be wrapped in a context that provides nodeId
 */
export function useAutoNodeState<T>(
  stateKey: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const nodeId = useNodeId();
  
  if (!nodeId) {
    throw new Error('useAutoNodeState requires a valid node ID. Use useNodeState with explicit nodeId instead.');
  }
  
  return useNodeState(nodeId, stateKey, defaultValue);
} 