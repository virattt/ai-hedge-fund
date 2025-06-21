import { AppNode } from '@/nodes/types';
import { FlowStorageService } from '@/services/flow-storage';
import { Edge } from '@xyflow/react';
import { useCallback, useEffect } from 'react';
import { useToastManager } from './use-toast-manager';

interface UseFlowPersistenceProps {
  rfInstance: any;
  nodes: AppNode[];
  edges: Edge[];
  setNodes: (nodes: AppNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  setViewport: (viewport: { x: number; y: number; zoom: number }) => void;
  isInitialized: boolean;
}

export function useFlowPersistence({
  rfInstance,
  nodes,
  edges,
  setNodes,
  setEdges,
  setViewport,
  isInitialized,
}: UseFlowPersistenceProps) {
  const { success, error } = useToastManager();

  // Save current flow state to localStorage
  const saveFlow = useCallback((showToast = false) => {
    if (rfInstance) {
      const flow = rfInstance.toObject();
      const saveSuccess = FlowStorageService.saveFlow(flow);
      
      if (saveSuccess) {
        console.log('Flow saved to localStorage');
        
        if (showToast) {
          success('Saved!', 'flow-save');
        }
      } else {
        console.error('Failed to save flow');
        if (showToast) {
          error('Failed to save flow', 'flow-save-error');
        }
      }
    }
  }, [rfInstance, success, error]);

  // Load saved flow on component mount
  const restoreFlow = useCallback(async () => {
    const flowState = FlowStorageService.loadFlow();
    
    if (flowState) {
      try {
        const { x = 0, y = 0, zoom = 1 } = flowState.viewport;
        
        if (flowState.nodes) {
          setNodes(flowState.nodes);
        }
        if (flowState.edges) {
          setEdges(flowState.edges);
        }
        setViewport({ x, y, zoom });
      } catch (error) {
        console.error('Failed to restore flow:', error);
      }
    }
  }, [setNodes, setEdges, setViewport]);

  // Clear saved flow data
  const clearSavedFlow = useCallback(() => {
    const clearSuccess = FlowStorageService.clearFlow();
    
    if (clearSuccess) {
      success('Reset successful!', 'flow-reset');
    } else {
      error('Failed to reset flow', 'flow-reset-error');
    }
  }, [success, error]);

  // Auto-save flow when nodes or edges change (with debounce)
  useEffect(() => {
    if (!rfInstance || !isInitialized) return;
    
    const timeoutId = setTimeout(() => {
      saveFlow(false); // Auto-save without toast
    }, 1000); // Save 1 second after last change

    return () => clearTimeout(timeoutId);
  }, [nodes, edges, rfInstance, isInitialized, saveFlow]);

  // Load saved flow on mount
  useEffect(() => {
    restoreFlow();
  }, [restoreFlow]);

  return {
    saveFlow,
    restoreFlow,
    clearSavedFlow,
    hasFlow: FlowStorageService.hasFlow(),
    flowSize: FlowStorageService.getFlowSize(),
  };
} 