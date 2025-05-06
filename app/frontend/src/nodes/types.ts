import type { BuiltInNode, Node } from '@xyflow/react';

export type PositionLoggerNode = Node<{ label: string }, 'position-logger'>;
export type AgentNode = Node<{ id: string, name: string, description: string, status: string }, 'agent'>;
export type AppNode = BuiltInNode | PositionLoggerNode | AgentNode;
