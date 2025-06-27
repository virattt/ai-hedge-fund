import { Edge, Node, useReactFlow } from '@xyflow/react';
import { useCallback, useRef, useState } from 'react';

interface FlowSnapshot {
  nodes: Node[];
  edges: Edge[];
  timestamp: number;
}

interface UseFlowHistoryOptions {
  maxHistorySize?: number;
}

export function useFlowHistory({ maxHistorySize = 50 }: UseFlowHistoryOptions = {}) {
  const { getNodes, getEdges, setNodes, setEdges } = useReactFlow();
  const [historyIndex, setHistoryIndex] = useState(-1);
  const history = useRef<FlowSnapshot[]>([]);
  const isUndoRedoAction = useRef(false);

  // Create a snapshot of current state
  const createSnapshot = useCallback((): FlowSnapshot => {
    return {
      nodes: JSON.parse(JSON.stringify(getNodes())),
      edges: JSON.parse(JSON.stringify(getEdges())),
      timestamp: Date.now(),
    };
  }, [getNodes, getEdges]);

  // Take a snapshot and add it to history
  const takeSnapshot = useCallback(() => {
    // Don't take snapshots during undo/redo operations
    if (isUndoRedoAction.current) {
      return;
    }

    const snapshot = createSnapshot();
    const newHistory = [...history.current];
    
    // If we're not at the end of history, remove future snapshots
    if (historyIndex < newHistory.length - 1) {
      newHistory.splice(historyIndex + 1);
    }
    
    // Add new snapshot
    newHistory.push(snapshot);
    
    // Limit history size
    if (newHistory.length > maxHistorySize) {
      newHistory.shift();
    } else {
      setHistoryIndex(prev => prev + 1);
    }
    
    history.current = newHistory;
    if (newHistory.length > maxHistorySize) {
      setHistoryIndex(maxHistorySize - 1);
    }
  }, [createSnapshot, historyIndex, maxHistorySize]);

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
    if (historyIndex > 0) {
      const prevSnapshot = history.current[historyIndex - 1];
      restoreSnapshot(prevSnapshot);
      setHistoryIndex(prev => prev - 1);
    }
  }, [historyIndex, restoreSnapshot]);

  // Redo next action
  const redo = useCallback(() => {
    if (historyIndex < history.current.length - 1) {
      const nextSnapshot = history.current[historyIndex + 1];
      restoreSnapshot(nextSnapshot);
      setHistoryIndex(prev => prev + 1);
    }
  }, [historyIndex, restoreSnapshot]);

  // Check if undo is available
  const canUndo = historyIndex > 0;
  
  // Check if redo is available
  const canRedo = historyIndex < history.current.length - 1;

  // Clear history
  const clearHistory = useCallback(() => {
    history.current = [];
    setHistoryIndex(-1);
  }, []);

  return {
    takeSnapshot,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,
  };
} 