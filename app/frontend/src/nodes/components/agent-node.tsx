import { type NodeProps } from '@xyflow/react';
import { Bot } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { CardContent } from '@/components/ui/card';
import { ModelSelector } from '@/components/ui/llm-selector';
import { useNodeContext } from '@/contexts/node-context';
import { getModels, LanguageModel } from '@/data/models';
import { cn } from '@/lib/utils';
import { type AgentNode } from '../types';
import { getStatusColor } from '../utils';
import { AgentOutputDialog } from './agent-output-dialog';
import { NodeShell } from './node-shell';

export function AgentNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<AgentNode>) {
  const { agentNodeData, setAgentModel, getAgentModel } = useNodeContext();
  const nodeData = agentNodeData[id] || { 
    status: 'IDLE', 
    ticker: null, 
    message: '', 
    messages: [],
    lastUpdated: 0
  };
  const status = nodeData.status;
  const isInProgress = status === 'IN_PROGRESS';
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [availableModels, setAvailableModels] = useState<LanguageModel[]>([]);
  
  // Get the current model for this agent (null if using global model)
  const currentModel = getAgentModel(id);
  const [selectedModel, setSelectedModel] = useState<LanguageModel | null>(currentModel);

  // Load models on mount
  useEffect(() => {
    const loadModels = async () => {
      try {
        const models = await getModels();
        setAvailableModels(models);
      } catch (error) {
        console.error('Failed to load models:', error);
        // Keep empty array as fallback
      }
    };
    
    loadModels();
  }, []);

  // Update the node context when the model changes
  useEffect(() => {
    if (selectedModel !== currentModel) {
      setAgentModel(id, selectedModel);
    }
  }, [selectedModel, id, setAgentModel, currentModel]);

  const handleModelChange = (model: LanguageModel | null) => {
    setSelectedModel(model);
  };

  const handleUseGlobalModel = () => {
    setSelectedModel(null);
  };

  return (
    <NodeShell
      id={id}
      selected={selected}
      isConnectable={isConnectable}
      icon={<Bot className="h-5 w-5" />}
      iconColor={getStatusColor(status)}
      name={data.name || "Agent"}
      description={data.description}
      status={status}
    >
      <CardContent className="p-0">
        <div className="border-t border-border p-3">
          <div className="flex flex-col gap-2">
            <div className="text-subtitle text-muted-foreground flex items-center gap-1">
              Status
            </div>

            <div className={cn(
              "text-foreground text-xs rounded p-2",
              isInProgress ? "gradient-animation" : getStatusColor(status)
            )}>
              <span className="capitalize">{status.toLowerCase().replace(/_/g, ' ')}</span>
            </div>
            
            {nodeData.message && (
              <div className="text-foreground text-subtitle">
                {nodeData.message}
                {nodeData.ticker && <span className="ml-1">({nodeData.ticker})</span>}
              </div>
            )}
            <Accordion type="single" collapsible>
              <AccordionItem value="advanced" className="border-none">
                <AccordionTrigger className="!text-subtitle text-muted-foreground">
                  Advanced
                </AccordionTrigger>
                <AccordionContent className="pt-2">
                  <div className="flex flex-col gap-2">
                    <div className="text-subtitle text-muted-foreground flex items-center gap-1">
                      Model
                    </div>
                    <ModelSelector
                      models={availableModels}
                      value={selectedModel?.model_name || ""}
                      onChange={handleModelChange}
                      placeholder="Auto"
                    />
                    {selectedModel && (
                      <button
                        onClick={handleUseGlobalModel}
                        className="text-subtitle text-muted-foreground hover:text-foreground transition-colors text-left"
                      >
                        Reset to Auto
                      </button>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>
        </div>
        <AgentOutputDialog
          isOpen={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          name={data.name || "Agent"}
          nodeId={id}
        />
      </CardContent>
    </NodeShell>
  );
}
