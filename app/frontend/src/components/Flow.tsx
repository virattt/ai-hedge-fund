import {
  Background,
  ColorMode,
  Controls,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
  type OnConnect
} from '@xyflow/react';
import { useCallback, useState } from 'react';

import '@xyflow/react/dist/style.css';

import { edgeTypes, initialEdges } from '../edges';
import { initialNodes, nodeTypes } from '../nodes';

type FlowProps = {
  className?: string;
};

export function Flow({ className = '' }: FlowProps) {
  const [colorMode] = useState<ColorMode>('dark');
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const proOptions = { hideAttribution: true };
  
  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((edges) => addEdge(connection, edges)),
    [setEdges]
  );

  return (
    <div className={`w-full h-full ${className}`}>
      <ReactFlow
        nodes={nodes}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        edges={edges}
        edgeTypes={edgeTypes}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        colorMode={colorMode}
        proOptions={proOptions}
        fitView
      >
        <Background gap={13}/>
        <Controls />
      </ReactFlow>
    </div>
  );
} 