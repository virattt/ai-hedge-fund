import { Edge, type NodeTypes } from '@xyflow/react';

import { AgentNode } from './components/agent-node';
import { InvestmentReportNode } from './components/investment-report-node';
import { JsonOutputNode } from './components/json-output-node';
import { PortfolioManagerNode } from './components/portfolio-manager-node';
import { type AppNode } from './types';

// Types
export * from './types';

export const initialNodes: AppNode[] = [
  {
    id: 'portfolio-manager-node',
    type: 'portfolio-manager-node',
    position: { x: 0, y: 0 },
    data: {
      name: 'Portfolio Manager',
      description: 'Start Node',
      status: 'Idle',
    },
  },
  {
    id: 'valuation_analyst',
    type: 'agent-node',
    position: { x: 300, y: 25 },
    data: {
      name: 'Valuation Analyst',
      description: 'Company Valuation Specialist',
      status: 'Idle',
    },
  },
  {
    id: 'investment-report-node',
    type: 'investment-report-node',
    position: { x: 600, y: 75 },
    data: {
      name: 'Investment Report',
      description: 'End Node',
      status: 'Idle',
    },
  },
];

export const initialEdges: Edge[] = [
  { id: 'e1-2', source: 'portfolio-manager-node', target: 'valuation_analyst' },
  { id: 'e2-3', source: 'valuation_analyst', target: 'investment-report-node' },
];

export const nodeTypes = {
  'agent-node': AgentNode,
  'portfolio-manager-node': PortfolioManagerNode,
  'investment-report-node': InvestmentReportNode,
  'json-output-node': JsonOutputNode,
} satisfies NodeTypes;
