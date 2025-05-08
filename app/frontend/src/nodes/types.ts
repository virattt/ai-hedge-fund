import type { BuiltInNode, Node } from '@xyflow/react';

export type AgentNode = Node<{ id: string, name: string, description: string, status: string }, 'agent'>;
export type StartNode = Node<{ id: string, name: string, description: string, status: string }, 'start'>;
export type AppNode = BuiltInNode | AgentNode | StartNode;
