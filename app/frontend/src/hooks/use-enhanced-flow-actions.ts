import { useFlowContext } from '@/contexts/flow-context';
import { useNodeContext } from '@/contexts/node-context';
import {
    getNodeInternalState,
    setNodeInternalState,
    setCurrentFlowId as setNodeStateFlowId
} from '@/hooks/use-node-state';
import { flowService } from '@/services/flow-service';
import { Flow } from '@/types/flow';
import { useCallback } from 'react';

/**
 * Enhanced flow actions that include complete state persistence
 * (both use-node-state data and node context data)
 */
export function useEnhancedFlowActions() {
  const { saveCurrentFlow, loadFlow, reactFlowInstance, currentFlowId } = useFlowContext();
  const { exportNodeContextData, resetAllNodes } = useNodeContext();

  // Enhanced save that includes node context data
  const saveCurrentFlowWithCompleteState = useCallback(async (name?: string, description?: string): Promise<Flow | null> => {
    try {
      // Get current nodes from React Flow
      const currentNodes = reactFlowInstance.getNodes();
      
      // Get node context data (runtime data: agent status, messages, output data)
      const flowId = currentFlowId?.toString() || null;
      const nodeContextData = exportNodeContextData(flowId);
      
      // Enhance nodes with internal states
      const nodesWithStates = currentNodes.map((node: any) => {
        const internalState = getNodeInternalState(node.id);
        return {
          ...node,
          data: {
            ...node.data,
            // Only add internal_state if there is actually state to save
            ...(internalState && Object.keys(internalState).length > 0 ? { internal_state: internalState } : {})
          }
        };
      });

      // Temporarily replace nodes in React Flow with enhanced nodes
      reactFlowInstance.setNodes(nodesWithStates);
      
      try {
        // Use the basic save function
        const savedFlow = await saveCurrentFlow(name, description);
        
        if (savedFlow) {
          // After basic save, update with node context data
          const updatedFlow = await flowService.updateFlow(savedFlow.id, {
            ...savedFlow,
            data: {
              ...savedFlow.data,
              nodeContextData, // Add runtime data from node context
            }
          });
          
          return updatedFlow;
        }
        
        return savedFlow;
      } finally {
        // Restore original nodes (without internal_state in React Flow)
        reactFlowInstance.setNodes(currentNodes);
      }
    } catch (err) {
      console.error('Failed to save flow with complete state:', err);
      return null;
    }
  }, [reactFlowInstance, saveCurrentFlow, exportNodeContextData, currentFlowId]);

  // Enhanced load that restores node context data
  const loadFlowWithCompleteState = useCallback(async (flow: Flow) => {
    try {
      // First, set the flow ID for node state isolation
      setNodeStateFlowId(flow.id.toString());
      
      // DO NOT clear configuration state when loading flows - useNodeState handles flow isolation automatically
      // DO NOT reset runtime data when loading flows - preserve all runtime state
      // Runtime data should only be reset when explicitly starting a new run via the Play button
      console.log(`[EnhancedFlowActions] Loading flow ${flow.id} (${flow.name}), preserving all state (configuration + runtime)`);

      // Load the flow using the basic function (handles React Flow state)
      await loadFlow(flow);

      // Then restore internal states for each node (use-node-state data)
      if (flow.nodes) {
        flow.nodes.forEach((node: any) => {
          if (node.data?.internal_state) {
            setNodeInternalState(node.id, node.data.internal_state);
          }
        });
      }
      
      // NOTE: We intentionally do NOT restore nodeContextData here
      // Runtime execution data (messages, analysis, agent status) should start fresh
      // Only configuration data (tickers, model selections) is restored above

      console.log('Flow loaded with complete state restoration:', flow.name);
    } catch (error) {
      console.error('Failed to load flow with complete state:', error);
      throw error;
    }
  }, [loadFlow]);

  return {
    saveCurrentFlowWithCompleteState,
    loadFlowWithCompleteState,
  };
} 