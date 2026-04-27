import { type NodeProps } from '@xyflow/react';
import { Brain } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { CardContent } from '@/components/ui/card';
import { ModelSelector } from '@/components/ui/llm-selector';
import { useFlowContext } from '@/contexts/flow-context';
import { useNodeContext } from '@/contexts/node-context';
import { getDefaultModel, getModels, LanguageModel } from '@/data/models';
import { useNodeState } from '@/hooks/use-node-state';
import { useOutputNodeConnection } from '@/hooks/use-output-node-connection';
import { cn } from '@/lib/utils';
import { type PortfolioManagerNode } from '../types';
import { getStatusColor } from '../utils';
import { InvestmentReportDialog } from './investment-report-dialog';
import { NodeShell } from './node-shell';

export function PortfolioManagerNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<PortfolioManagerNode>) {
  const { currentFlowId } = useFlowContext();
  const { getAgentNodeDataForFlow, setAgentModel, getAgentModel, getOutputNodeDataForFlow } = useNodeContext();

  // Get agent node data for the current flow
  const agentNodeData = getAgentNodeDataForFlow(currentFlowId?.toString() || null);
  const nodeData = agentNodeData[id] || {
    status: 'IDLE',
    ticker: null,
    message: '',
    messages: [],
    lastUpdated: 0,
  };
  const status = nodeData.status;
  const isInProgress = status === 'IN_PROGRESS';
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Use persistent state hooks
  const [availableModels, setAvailableModels] = useNodeState<LanguageModel[]>(
    id,
    'availableModels',
    []
  );
  const [selectedModel, setSelectedModel] = useNodeState<LanguageModel | null>(
    id,
    'selectedModel',
    null
  );

  // Load models on mount
  useEffect(() => {
    const loadModels = async () => {
      try {
        const [models, defaultModel] = await Promise.all([
          getModels(),
          getDefaultModel()
        ]);
        setAvailableModels(models);
        
        // Set default model if no model is currently selected
        if (!selectedModel && defaultModel) {
          setSelectedModel(defaultModel);
        }
      } catch (error) {
        console.error('Failed to load models:', error);
        // Keep empty array as fallback
      }
    };

    loadModels();
  }, [setAvailableModels, selectedModel, setSelectedModel]);

  // Update the node context when the model changes
  useEffect(() => {
    const flowId = currentFlowId?.toString() || null;
    const currentContextModel = getAgentModel(flowId, id);
    if (selectedModel !== currentContextModel) {
      setAgentModel(flowId, id, selectedModel);
    }
  }, [selectedModel, id, currentFlowId, setAgentModel, getAgentModel]);

  const handleModelChange = (model: LanguageModel | null) => {
    setSelectedModel(model);
  };
  
  const outputNodeData = getOutputNodeDataForFlow(currentFlowId?.toString() || null);

  // Get connected agent IDs
  const { connectedAgentIds } = useOutputNodeConnection(id);

  return (
    <>
      <NodeShell
        id={id}
        selected={selected}
        isConnectable={isConnectable}
        icon={<Brain className="h-5 w-5" />}
        iconColor={getStatusColor(status)}
        name={data.name || 'Portfolio Manager'}
        description={data.description}
        hasRightHandle={false}
        status={status}
      >
        <CardContent className="p-0">
          <div className="border-t border-border p-3">
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <div className="text-subtitle text-primary flex items-center gap-1">
                  Status
                </div>

                <div
                  className={cn(
                    'text-foreground text-xs rounded p-2 border border-status',
                    isInProgress ? 'gradient-animation' : getStatusColor(status)
                  )}
                >
                  <span className="capitalize">
                    {status.toLowerCase().replace(/_/g, ' ')}
                  </span>
                </div>
              </div>
              <div className='flex flex-col gap-2'>
                {outputNodeData && (
                  <Button
                    size="sm"
                    onClick={() => setIsDialogOpen(true)}
                  >
                    View Investment Report
                  </Button>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <div className="text-subtitle text-primary flex items-center gap-1">
                  Model
                </div>
                <ModelSelector
                  models={availableModels}
                  value={selectedModel?.model_name || ''}
                  onChange={handleModelChange}
                  placeholder="Auto"
                />
              </div>
            </div>
          </div>
          <InvestmentReportDialog
            isOpen={isDialogOpen}
            onOpenChange={setIsDialogOpen}
            outputNodeData={outputNodeData}
            connectedAgentIds={connectedAgentIds}
          />
        </CardContent>
      </NodeShell>
    </>
  );
}
