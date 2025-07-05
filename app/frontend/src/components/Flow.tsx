import {
  Background,
  ColorMode,
  Connection,
  Edge,
  EdgeChange,
  MarkerType,
  NodeChange,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState
} from '@xyflow/react';
import { useCallback, useEffect, useRef, useState } from 'react';

import '@xyflow/react/dist/style.css';

import { useFlowContext } from '@/contexts/flow-context';
import { useEnhancedFlowActions } from '@/hooks/use-enhanced-flow-actions';
import { useFlowHistory } from '@/hooks/use-flow-history';
import { useFlowKeyboardShortcuts, useKeyboardShortcuts } from '@/hooks/use-keyboard-shortcuts';
import { useToastManager } from '@/hooks/use-toast-manager';
import { AppNode } from '@/nodes/types';
import { edgeTypes } from '../edges';
import { nodeTypes } from '../nodes';
import { TooltipProvider } from './ui/tooltip';

type FlowProps = {
  className?: string;
};

export function Flow({ className = '' }: FlowProps) {
  const [colorMode] = useState<ColorMode>('dark');
  const [nodes, setNodes, onNodesChange] = useNodesState<AppNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [isInitialized, setIsInitialized] = useState(false);
  const proOptions = { hideAttribution: true };
  
  // Get flow context for flow ID
  const { currentFlowId } = useFlowContext();
  
  // Get enhanced flow actions for complete state persistence
  const { saveCurrentFlowWithCompleteState } = useEnhancedFlowActions();
  
  // Get toast manager
  const { success, error } = useToastManager();

  // Initialize flow history (each flow maintains its own separate history)
  const { takeSnapshot, undo, redo, canUndo, canRedo, clearHistory } = useFlowHistory({ flowId: currentFlowId });

  // Create debounced auto-save function
  const autoSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedFlowIdRef = useRef<number | null>(null);
  
  const autoSave = useCallback(async (flowIdToSave?: number | null) => {
    // Use the provided flowId or fall back to current flow ID
    const targetFlowId = flowIdToSave !== undefined ? flowIdToSave : currentFlowId;
    
    // Clear any existing timeout
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current);
    }
    
    // Set new timeout for debounced save
    autoSaveTimeoutRef.current = setTimeout(async () => {
      // Double-check that we're still saving to the correct flow
      if (!targetFlowId) {
        return;
      }
      
      // If the current flow has changed since this auto-save was scheduled, skip it
      if (targetFlowId !== currentFlowId) {
        return;
      }
      
      try {
        await saveCurrentFlowWithCompleteState();
        lastSavedFlowIdRef.current = targetFlowId;
      } catch (error) {
        console.error(`[Auto-save] Failed to save flow ${targetFlowId}:`, error);
      }
    }, 1000); // 1 second debounce
  }, [currentFlowId, saveCurrentFlowWithCompleteState]);

  // Enhanced onNodesChange handler with auto-save for specific change types
  const handleNodesChange = useCallback((changes: NodeChange<AppNode>[]) => {
    // Apply the changes first
    onNodesChange(changes);
    
    // Check if any of the changes should trigger auto-save
    const shouldAutoSave = changes.some(change => {
      switch (change.type) {
        case 'add':
          return true;
        case 'remove':
          return true;
        case 'position':
          // Only auto-save position changes when dragging is complete
          if (!change.dragging) {
            return true;
          }
          return false;
        default:
          return false;
      }
    });

    // Trigger auto-save if needed and flow is initialized
    // IMPORTANT: Capture the current flow ID at the time of the change
    if (shouldAutoSave && isInitialized && currentFlowId) {
      const flowIdAtTimeOfChange = currentFlowId;
      autoSave(flowIdAtTimeOfChange);
    }
  }, [onNodesChange, autoSave, isInitialized, currentFlowId]);

  // Enhanced onEdgesChange handler with auto-save for edge removal
  const handleEdgesChange = useCallback((changes: EdgeChange[]) => {
    // Apply the changes first
    onEdgesChange(changes);
    
    // Check if any of the changes should trigger auto-save
    const shouldAutoSave = changes.some(change => {
      switch (change.type) {
        case 'remove':
          return true;
        default:
          return false;
      }
    });

    // Trigger auto-save if needed and flow is initialized
    // IMPORTANT: Capture the current flow ID at the time of the change
    if (shouldAutoSave && isInitialized && currentFlowId) {
      const flowIdAtTimeOfChange = currentFlowId;
      autoSave(flowIdAtTimeOfChange);
    }
  }, [onEdgesChange, autoSave, isInitialized, currentFlowId]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current);
      }
    };
  }, []);

  // Cancel pending auto-saves when flow changes to prevent cross-flow saves
  useEffect(() => {
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current);
      autoSaveTimeoutRef.current = null;
    }
  }, [currentFlowId]);

  // Take initial snapshot when flow is initialized
  useEffect(() => {
    if (isInitialized && nodes.length === 0 && edges.length === 0) {
      takeSnapshot();
    }
  }, [isInitialized, takeSnapshot, nodes.length, edges.length]);

  // Take snapshot when nodes or edges change (debounced)
  useEffect(() => {
    if (!isInitialized) return;
    
    const timeoutId = setTimeout(() => {
      takeSnapshot();
    }, 500); // Debounce snapshots by 500ms

    return () => clearTimeout(timeoutId);
  }, [nodes, edges, takeSnapshot, isInitialized]);

  // // Auto-save when nodes or edges change (debounced with longer delay)
  // useEffect(() => {
  //   if (!isInitialized) return;
    
  //   const timeoutId = setTimeout(async () => {
  //     try {
  //       await saveCurrentFlowWithCompleteState();
  //       // Don't show success toast for auto-save to avoid spam
  //     } catch (err) {
  //       // Only show error notifications for auto-save failures
  //       error('Auto-save failed', 'auto-save-error');
  //     }
  //   }, 1000); // Debounce auto-save by 1 second (longer than undo/redo)

  //   return () => clearTimeout(timeoutId);
  // }, [nodes, edges, saveCurrentFlowWithCompleteState, error, isInitialized]);

  // Connect keyboard shortcuts to save flow with toast
  useFlowKeyboardShortcuts(async () => {
    try {
      const savedFlow = await saveCurrentFlowWithCompleteState();
      if (savedFlow) {
        success(`"${savedFlow.name}" saved!`, 'flow-save');
      } else {
        error('Failed to save flow', 'flow-save-error');
      }
    } catch (err) {
      error('Failed to save flow', 'flow-save-error');
    }
  });

  // Add undo/redo keyboard shortcuts
  useKeyboardShortcuts({
    shortcuts: [
      {
        key: 'z',
        ctrlKey: true,
        metaKey: true,
        callback: undo,
        preventDefault: true,
      },
      {
        key: 'z',
        ctrlKey: true,
        metaKey: true,
        shiftKey: true,
        callback: redo,
        preventDefault: true,
      },
    ],
  });
  
  // Initialize the flow when it first renders
  const onInit = useCallback(() => {
    if (!isInitialized) {
      setIsInitialized(true);
    }
  }, [isInitialized]);

  // Connect two nodes with marker
  const onConnect = useCallback(
    (connection: Connection) => {
      // Create a new edge with a marker and unique ID
      const newEdge: Edge = {
        ...connection,
        id: `edge-${Date.now()}`, // Add unique ID
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      };
      setEdges((eds) => addEdge(newEdge, eds));
      
      // Auto-save new connections immediately (structural change)
      if (currentFlowId) {
        // IMPORTANT: Capture the current flow ID at the time of the change
        const flowIdAtTimeOfChange = currentFlowId;
        
        // Clear any pending debounced saves and save immediately
        if (autoSaveTimeoutRef.current) {
          clearTimeout(autoSaveTimeoutRef.current);
        }
        
        // Use setTimeout to ensure the edge is added to state first
        setTimeout(async () => {
          // Double-check that we're still saving to the correct flow
          if (flowIdAtTimeOfChange !== currentFlowId) {
            return;
          }
          
          try {
            await saveCurrentFlowWithCompleteState();
          } catch (error) {
            console.error(`[Auto-save] Failed to save new connection for flow ${flowIdAtTimeOfChange}:`, error);
          }
        }, 100);
      }
    },
    [setEdges, currentFlowId, saveCurrentFlowWithCompleteState]
  );

  return (
    <div className={`w-full h-full ${className}`}>
      <TooltipProvider>
        <ReactFlow
          nodes={nodes}
          nodeTypes={nodeTypes}
          onNodesChange={handleNodesChange}
          edges={edges}
          edgeTypes={edgeTypes}
          onEdgesChange={handleEdgesChange}
          onConnect={onConnect}
          onInit={onInit}
          colorMode={colorMode}
          proOptions={proOptions}
        >
          <Background 
            gap={13}
            color="#666666"
            style={{ backgroundColor: '#0a0a0a' }}
          />
          {/* <CustomControls onReset={resetFlow} /> */}
        </ReactFlow>
      </TooltipProvider>
    </div>
  );
} 