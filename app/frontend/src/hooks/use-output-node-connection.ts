import { getConnectedEdges, useReactFlow } from '@xyflow/react';
import { useMemo } from 'react';

import { useFlowContext } from '@/contexts/flow-context';
import { useNodeContext } from '@/contexts/node-context';

/**
 * Custom hook to determine output node connection state and processing status
 * @param nodeId - The ID of the output node
 * @returns Object containing connection state and processing status
 */
export function useOutputNodeConnection(nodeId: string) {
  const { currentFlowId } = useFlowContext();
  const { getAgentNodeDataForFlow, getOutputNodeDataForFlow } = useNodeContext();
  const { getNodes, getEdges } = useReactFlow();

  // Get data for the current flow
  const flowId = currentFlowId?.toString() || null;
  const agentNodeData = getAgentNodeDataForFlow(flowId);
  const outputNodeData = getOutputNodeDataForFlow(flowId);

  return useMemo(() => {
    // Get all nodes and edges
    const nodes = getNodes();
    const edges = getEdges();
    
    // Find edges connected to this output node
    const connectedEdges = getConnectedEdges([{ id: nodeId }] as any, edges);
    const connectedAgentIds = connectedEdges
      .filter(edge => edge.target === nodeId)
      .map(edge => edge.source)
      .filter(sourceId => {
        const sourceNode = nodes.find(n => n.id === sourceId);
        return sourceNode?.type === 'agent-node';
      });

    // Check if any connected agents are running
    const isAnyAgentRunning = connectedAgentIds.some(agentId => 
      agentNodeData[agentId]?.status === 'IN_PROGRESS'
    );

    // Check if processing (any agent is running)
    const isProcessing = isAnyAgentRunning;

    // Check if output is available
    const isOutputAvailable = outputNodeData !== null && outputNodeData !== undefined;

    // Check if connected to any agents  
    const isConnected = connectedAgentIds.length > 0;

    return {
      isProcessing,
      isAnyAgentRunning,
      isOutputAvailable,
      isConnected,
      connectedAgentIds: new Set(connectedAgentIds),
    };
  }, [nodeId, agentNodeData, outputNodeData, getNodes, getEdges]);
} 