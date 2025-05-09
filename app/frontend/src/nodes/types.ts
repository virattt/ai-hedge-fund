import type { BuiltInNode, Node } from '@xyflow/react';

export type AgentNode = Node<{ name: string, description: string, status: string }, 'agent'>;
export type StartNode = Node<{ name: string, description: string, status: string }, 'start'>;
export type AppNode = BuiltInNode | AgentNode | StartNode;
