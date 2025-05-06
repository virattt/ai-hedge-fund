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

import { edgeTypes, initialEdges } from './edges';
import { initialNodes, nodeTypes } from './nodes';

export default function App() {
  const [colorMode, setColorMode] = useState<ColorMode>('dark');
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const proOptions = { hideAttribution: true };
  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((edges) => addEdge(connection, edges)),
    [setEdges]
  );

  return (
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
      <Background />
      {/* <MiniMap /> */}
      <Controls />
    </ReactFlow>
  );
}
