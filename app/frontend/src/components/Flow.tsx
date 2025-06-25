import {
  Background,
  ColorMode,
  Connection,
  Edge,
  MarkerType,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState
} from '@xyflow/react';
import { useCallback, useEffect, useState } from 'react';

import '@xyflow/react/dist/style.css';

import { useFlowContext } from '@/contexts/flow-context';
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
  
  // Get flow context for saving
  const { saveCurrentFlow } = useFlowContext();
  
  // Get toast manager
  const { success, error } = useToastManager();

  // Initialize flow history
  const { takeSnapshot, undo, redo, canUndo, canRedo, clearHistory } = useFlowHistory();

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

  // Connect keyboard shortcuts to save flow with toast
  useFlowKeyboardShortcuts(async () => {
    try {
      const savedFlow = await saveCurrentFlow();
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
    },
    [setEdges]
  );

  // Reset the flow to initial state
  const resetFlow = useCallback(() => {
    setNodes([]);
    setEdges([]);
    clearHistory();
  }, [setNodes, setEdges, clearHistory]);

  return (
    <div className={`w-full h-full ${className}`}>
      <TooltipProvider>
        <ReactFlow
          nodes={nodes}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          edges={edges}
          edgeTypes={edgeTypes}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onInit={onInit}
          colorMode={colorMode}
          proOptions={proOptions}
        >
          <Background gap={13}/>
          {/* <CustomControls onReset={resetFlow} /> */}
        </ReactFlow>
      </TooltipProvider>
    </div>
  );
} 