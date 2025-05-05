import type { BuiltInNode, Node } from '@xyflow/react';

export type PositionLoggerNode = Node<{ label: string }, 'position-logger'>;
export type AgentNode = Node<{ agent_name: string; agent_id: string }, 'agent'>;
export type AppNode = BuiltInNode | PositionLoggerNode | AgentNode;
