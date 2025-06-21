import {
  Background,
  ColorMode,
  Connection,
  Edge,
  MarkerType,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow
} from '@xyflow/react';
import { useCallback, useState } from 'react';

import '@xyflow/react/dist/style.css';

import { useFlowPersistence } from '@/hooks/use-flow-persistence';
import { useFlowKeyboardShortcuts } from '@/hooks/use-keyboard-shortcuts';
import { AppNode } from '@/nodes/types';
import { edgeTypes } from '../edges';
import { initialEdges, initialNodes, nodeTypes } from '../nodes';
import { CustomControls } from './custom-controls';
import { TooltipProvider } from './ui/tooltip';

type FlowProps = {
  className?: string;
};

export function Flow({ className = '' }: FlowProps) {
  const [colorMode] = useState<ColorMode>('dark');
  const [nodes, setNodes, onNodesChange] = useNodesState<AppNode>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialEdges);
  const [isInitialized, setIsInitialized] = useState(false);
  const [rfInstance, setRfInstance] = useState<any>(null);
  const { setViewport } = useReactFlow();
  const proOptions = { hideAttribution: true };
  
  // Custom hooks for flow persistence and keyboard shortcuts
  const { saveFlow, clearSavedFlow } = useFlowPersistence({
    rfInstance,
    nodes,
    edges,
    setNodes,
    setEdges,
    setViewport,
    isInitialized,
  });
  
  useFlowKeyboardShortcuts(saveFlow);
  
  // Initialize the flow when it first renders
  const onInit = useCallback((reactFlowInstance: any) => {
    if (!isInitialized) {
      setIsInitialized(true);
      setRfInstance(reactFlowInstance);
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
    setNodes(initialNodes);
    setEdges(initialEdges);
    clearSavedFlow();
  }, [setNodes, setEdges, clearSavedFlow]);

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
          fitView
        >
          <Background gap={13}/>
          <CustomControls onReset={resetFlow} />
        </ReactFlow>
      </TooltipProvider>
    </div>
  );
} 