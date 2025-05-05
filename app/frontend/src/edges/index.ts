import type { Edge, EdgeTypes } from '@xyflow/react';

export const initialEdges: Edge[] = [
  { id: 'a->b', source: 'a', target: 'b', animated: true },
  { id: 'b->c', source: 'b', target: 'c', animated: true },
];

export const edgeTypes = {
  // Add your custom edge types here!
} satisfies EdgeTypes;
