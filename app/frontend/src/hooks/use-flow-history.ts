import { Edge, Node, useReactFlow } from '@xyflow/react';
import { useCallback, useRef, useState } from 'react';

interface FlowSnapshot {
  nodes: Node[];
  edges: Edge[];
  timestamp: number;
}

interface UseFlowHistoryOptions {
  maxHistorySize?: number;
  flowId?: number | null;
}

export function useFlowHistory({ maxHistorySize = 50, flowId }: UseFlowHistoryOptions = {}) {
  const { getNodes, getEdges, setNodes, setEdges } = useReactFlow();
  const [historyIndexes, setHistoryIndexes] = useState<Record<string, number>>({});
  const histories = useRef<Record<string, FlowSnapshot[]>>({});
  const isUndoRedoAction = useRef(false);

  // Get flow-specific history key
  const getFlowKey = useCallback((id: number | null) => {
    return id ? `flow-${id}` : 'new-flow';
  }, []);

  // Get current flow's history and index
  const getCurrentFlowHistory = useCallback(() => {
    const flowKey = getFlowKey(flowId ?? null);
    if (!histories.current[flowKey]) {
      histories.current[flowKey] = [];
    }
    return histories.current[flowKey];
  }, [flowId, getFlowKey]);

  const getCurrentHistoryIndex = useCallback(() => {
    const flowKey = getFlowKey(flowId ?? null);
    return historyIndexes[flowKey] ?? -1;
  }, [flowId, getFlowKey, historyIndexes]);

  const setCurrentHistoryIndex = useCallback((index: number) => {
    const flowKey = getFlowKey(flowId ?? null);
    setHistoryIndexes(prev => ({ ...prev, [flowKey]: index }));
  }, [flowId, getFlowKey]);

  // Create a snapshot of current state (excluding UI-only properties)
  const createSnapshot = useCallback((): FlowSnapshot => {
    // Strip UI-only properties from nodes (like selection state)
    const cleanNodes = getNodes().map(node => {
      const { selected, ...cleanNode } = node;
      return cleanNode;
    });

    // Create clean copies
    return {
      nodes: JSON.parse(JSON.stringify(cleanNodes)),
      edges: JSON.parse(JSON.stringify(getEdges())),
      timestamp: Date.now(),
    };
  }, [getNodes, getEdges]);

  // Check if two snapshots are meaningfully different (ignoring UI-only changes)
  const snapshotsAreDifferent = useCallback((snapshot1: FlowSnapshot, snapshot2: FlowSnapshot): boolean => {
    // Compare serialized versions to check for meaningful differences
    const nodes1Str = JSON.stringify(snapshot1.nodes);
    const nodes2Str = JSON.stringify(snapshot2.nodes);
    const edges1Str = JSON.stringify(snapshot1.edges);
    const edges2Str = JSON.stringify(snapshot2.edges);
    
    return nodes1Str !== nodes2Str || edges1Str !== edges2Str;
  }, []);

  // Take a snapshot and add it to history
  const takeSnapshot = useCallback(() => {
    // Don't take snapshots during undo/redo operations
    if (isUndoRedoAction.current) {
      return;
    }

    const snapshot = createSnapshot();
    const currentHistory = getCurrentFlowHistory();
    const currentIndex = getCurrentHistoryIndex();
    
    // Don't add duplicate snapshots (when only UI-only properties changed)
    if (currentHistory.length > 0) {
      const lastSnapshot = currentHistory[currentIndex];
      if (lastSnapshot && !snapshotsAreDifferent(snapshot, lastSnapshot)) {
        return; // Skip duplicate snapshot
      }
    }

    const newHistory = [...currentHistory];
    
    // If we're not at the end of history, remove future snapshots
    if (currentIndex < newHistory.length - 1) {
      newHistory.splice(currentIndex + 1);
    }
    
    // Add new snapshot
    newHistory.push(snapshot);
    
    // Update the flow's history
    const flowKey = getFlowKey(flowId ?? null);
    
    // Limit history size
    if (newHistory.length > maxHistorySize) {
      newHistory.shift();
      setCurrentHistoryIndex(maxHistorySize - 1);
    } else {
      setCurrentHistoryIndex(currentIndex + 1);
    }
    
    histories.current[flowKey] = newHistory;
  }, [createSnapshot, getCurrentFlowHistory, getCurrentHistoryIndex, maxHistorySize, snapshotsAreDifferent, getFlowKey, flowId, setCurrentHistoryIndex]);

  // Restore a snapshot
  const restoreSnapshot = useCallback((snapshot: FlowSnapshot) => {
    isUndoRedoAction.current = true;
    setNodes(snapshot.nodes);
    setEdges(snapshot.edges);
    // Reset flag after React has processed the state updates
    setTimeout(() => {
      isUndoRedoAction.current = false;
    }, 0);
  }, [setNodes, setEdges]);

  // Undo last action
  const undo = useCallback(() => {
    const currentIndex = getCurrentHistoryIndex();
    const currentHistory = getCurrentFlowHistory();
    
    if (currentIndex > 0) {
      const prevSnapshot = currentHistory[currentIndex - 1];
      restoreSnapshot(prevSnapshot);
      setCurrentHistoryIndex(currentIndex - 1);
    }
  }, [getCurrentHistoryIndex, getCurrentFlowHistory, restoreSnapshot, setCurrentHistoryIndex]);

  // Redo next action
  const redo = useCallback(() => {
    const currentIndex = getCurrentHistoryIndex();
    const currentHistory = getCurrentFlowHistory();
    
    if (currentIndex < currentHistory.length - 1) {
      const nextSnapshot = currentHistory[currentIndex + 1];
      restoreSnapshot(nextSnapshot);
      setCurrentHistoryIndex(currentIndex + 1);
    }
  }, [getCurrentHistoryIndex, getCurrentFlowHistory, restoreSnapshot, setCurrentHistoryIndex]);

  // Check if undo is available
  const canUndo = getCurrentHistoryIndex() > 0;
  
  // Check if redo is available
  const canRedo = getCurrentHistoryIndex() < getCurrentFlowHistory().length - 1;

  // Clear history for current flow
  const clearHistory = useCallback(() => {
    const flowKey = getFlowKey(flowId ?? null);
    histories.current[flowKey] = [];
    setCurrentHistoryIndex(-1);
  }, [getFlowKey, flowId, setCurrentHistoryIndex]);

  return {
    takeSnapshot,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,
  };
} 