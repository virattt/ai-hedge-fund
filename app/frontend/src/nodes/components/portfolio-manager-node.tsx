import { ModelSelector } from '@/components/ui/llm-selector';
import { getConnectedEdges, useReactFlow, type NodeProps } from '@xyflow/react';
import { Brain, Play, Square } from 'lucide-react';
import { useEffect } from 'react';

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Button } from '@/components/ui/button';
import { CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useFlowContext } from '@/contexts/flow-context';
import { useNodeContext } from '@/contexts/node-context';
import { getDefaultModel, getModels, LanguageModel } from '@/data/models';
import { useFlowConnection } from '@/hooks/use-flow-connection';
import { useKeyboardShortcuts } from '@/hooks/use-keyboard-shortcuts';
import { useNodeState } from '@/hooks/use-node-state';
import { formatKeyboardShortcut } from '@/lib/utils';
import { type PortfolioManagerNode } from '../types';
import { NodeShell } from './node-shell';

export function PortfolioManagerNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<PortfolioManagerNode>) {
  // Calculate default dates
  const today = new Date();
  const threeMonthsAgo = new Date(today);
  threeMonthsAgo.setMonth(today.getMonth() - 3);
  
  // Use persistent state hooks
  const [tickers, setTickers] = useNodeState(id, 'tickers', 'AAPL,NVDA,TSLA');
  const [selectedModel, setSelectedModel] = useNodeState<LanguageModel | null>(id, 'selectedModel', null);
  const [availableModels, setAvailableModels] = useNodeState<LanguageModel[]>(id, 'availableModels', []);
  const [startDate, setStartDate] = useNodeState(id, 'startDate', threeMonthsAgo.toISOString().split('T')[0]);
  const [endDate, setEndDate] = useNodeState(id, 'endDate', today.toISOString().split('T')[0]);
  
  const { currentFlowId } = useFlowContext();
  const nodeContext = useNodeContext();
  const { getAllAgentModels } = nodeContext;
  const { getNodes, getEdges } = useReactFlow();
  
  // Use the new flow connection hook
  const flowId = currentFlowId?.toString() || null;
  const {
    isConnecting,
    isConnected,
    isProcessing,
    canRun,
    runFlow,
    stopFlow,
    recoverFlowState
  } = useFlowConnection(flowId);
  
  // Check if the hedge fund can be run
  const canRunHedgeFund = canRun && tickers.trim() !== '';
  
  // Add keyboard shortcut for Cmd+Enter / Ctrl+Enter to run hedge fund
  useKeyboardShortcuts({
    shortcuts: [
      {
        key: 'Enter',
        ctrlKey: true,
        metaKey: true,
        callback: () => {
          if (canRunHedgeFund) {
            handlePlay();
          }
        },
        preventDefault: true,
      },
    ],
  });
  
  // Load models and set default on mount
  useEffect(() => {
    const loadModels = async () => {
      try {
        const [models, defaultModel] = await Promise.all([
          getModels(),
          getDefaultModel()
        ]);
        setAvailableModels(models);
        
        // Only set default model if no model is currently selected
        if (!selectedModel && defaultModel) {
          setSelectedModel(defaultModel);
        }
      } catch (error) {
        console.error('Failed to load models:', error);
        // Keep empty array and null as fallback
      }
    };
    
    loadModels();
  }, []); // Remove selectedModel from dependencies to avoid infinite loop

  // Recover flow state when component mounts or flow changes
  useEffect(() => {
    if (flowId) {
      recoverFlowState();
    }
  }, [flowId, recoverFlowState]);
  
  const handleTickersChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTickers(e.target.value);
  };

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setStartDate(e.target.value);
  };

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEndDate(e.target.value);
  };

  const handleStop = () => {
    stopFlow();
  };

  const handlePlay = () => {
    // Get the nodes and edges
    const nodes = getNodes();
    const edges = getEdges();
    const connectedEdges = getConnectedEdges(nodes, edges);
    
    // Get all nodes that are agents and are connected in the flow
    const selectedAgents = new Set<string>();
    
    // First, collect all the target node IDs from connected edges
    const connectedNodeIds = new Set<string>();
    connectedEdges.forEach(edge => {
      if (edge.source === id) {
        connectedNodeIds.add(edge.target);
      }
    });
    
    // Then filter for nodes that are agents
    nodes.forEach(node => {
      if (node.type === 'agent-node' && connectedNodeIds.has(node.id)) {
        selectedAgents.add(node.id);
      }
    });

    // Collect agent models from connected agent nodes
    const agentModels = [];
    const allAgentModels = getAllAgentModels(flowId);
    for (const agentId of selectedAgents) {
      const model = allAgentModels[agentId];
      if (model) {
        agentModels.push({
          agent_id: agentId,
          model_name: model.model_name,
          model_provider: model.provider as any
        });
      }
    }
    
    // Convert tickers to array    
    const tickerList = tickers.split(',').map(t => t.trim());
        
    // Use the flow connection hook to run the flow
    runFlow({
      tickers: tickerList,
      selected_agents: Array.from(selectedAgents),
      agent_models: agentModels,
      // Keep global model for backwards compatibility (will be removed later)
      model_name: selectedModel?.model_name || undefined,
      model_provider: selectedModel?.provider as any || undefined,
      start_date: startDate,
      end_date: endDate,
    });
  };

  // Determine if we're processing (connecting, connected, or any agents running)
  const showAsProcessing = isConnecting || isConnected || isProcessing;

  return (
    <TooltipProvider>
      <NodeShell
        id={id}
        selected={selected}
        isConnectable={isConnectable}
        icon={<Brain className="h-5 w-5" />}
        name={data.name || "Portfolio Manager"}
        description={data.description}
        hasLeftHandle={false}
      >
        <CardContent className="p-0">
          <div className="border-t border-border p-3">
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <div className="text-subtitle text-primary flex items-center gap-1">
                  <Tooltip delayDuration={200}>
                    <TooltipTrigger asChild>
                      <span>Tickers</span>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      You can add multiple tickers using commas (AAPL,NVDA,TSLA)
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder="Enter tickers"
                    value={tickers}
                    onChange={handleTickersChange}
                  />
                  <Button 
                    size="icon" 
                    variant="secondary"
                    className="flex-shrink-0 transition-all duration-200 hover:bg-primary hover:text-primary-foreground active:scale-95"
                    title={showAsProcessing ? "Stop" : `Run (${formatKeyboardShortcut('↵')})`}
                    onClick={showAsProcessing ? handleStop : handlePlay}
                    disabled={!canRunHedgeFund && !showAsProcessing}
                  >
                    {showAsProcessing ? (
                      <Square className="h-3.5 w-3.5" />
                    ) : (
                      <Play className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <div className="text-subtitle text-primary flex items-center gap-1">
                  Model
                </div>
                <ModelSelector
                  models={availableModels}
                  value={selectedModel?.model_name || ""}
                  onChange={setSelectedModel}
                  placeholder="Select a model..."
                />
              </div>
              <Accordion type="single" collapsible>
                <AccordionItem value="advanced" className="border-none">
                  <AccordionTrigger className="!text-subtitle text-primary">
                    Advanced
                  </AccordionTrigger>
                  <AccordionContent className="pt-2">
                    <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-2">
                        <div className="text-subtitle text-primary flex items-center gap-1">
                          End Date
                        </div>
                        <Input
                          type="date"
                          value={endDate}
                          onChange={handleEndDateChange}
                        />
                      </div>
                      <div className="flex flex-col gap-2">
                        <div className="text-subtitle text-primary flex items-center gap-1">
                          Start Date
                        </div>
                        <Input
                          type="date"
                          value={startDate}
                          onChange={handleStartDateChange}
                        />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          </div>
        </CardContent>
      </NodeShell>
    </TooltipProvider>
  );
}
