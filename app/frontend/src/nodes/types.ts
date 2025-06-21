import { MessageItem } from '@/contexts/node-context';
import type { BuiltInNode, Node } from '@xyflow/react';

export type NodeMessage = MessageItem;

export type AgentNode = Node<{ name: string, description: string, status: string }, 'agent-node'>;
export type PortfolioManagerNode = Node<{ name: string, description: string, status: string }, 'portfolio-manager-node'>;
export type InvestmentReportNode = Node<{ name: string, description: string, status: string }, 'investment-report-node'>;
export type JsonOutputNode = Node<{ name: string, description: string, status: string }, 'json-output-node'>;
export type AppNode = BuiltInNode | AgentNode | PortfolioManagerNode | InvestmentReportNode | JsonOutputNode;
