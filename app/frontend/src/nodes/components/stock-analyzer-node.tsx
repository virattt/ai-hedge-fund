import { useReactFlow, type NodeProps } from '@xyflow/react';
import { ChartLine, ChevronDown, Play, Square } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Button } from '@/components/ui/button';
import { CardContent } from '@/components/ui/card';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Input } from '@/components/ui/input';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useFlowContext } from '@/contexts/flow-context';
import { useLayoutContext } from '@/contexts/layout-context';
import { useNodeContext } from '@/contexts/node-context';
import { useFlowConnection } from '@/hooks/use-flow-connection';
import { useKeyboardShortcuts } from '@/hooks/use-keyboard-shortcuts';
import { useNodeState } from '@/hooks/use-node-state';
import { cn, formatKeyboardShortcut } from '@/lib/utils';
import { type StockAnalyzerNode } from '../types';
import { NodeShell } from './node-shell';

const runModes = [
  { value: 'single', label: 'Single Run' },
  { value: 'backtest', label: 'Backtest' },
];

export function StockAnalyzerNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<StockAnalyzerNode>) {
  // Calculate default dates
  const today = new Date();
  const threeMonthsAgo = new Date(today);
  threeMonthsAgo.setMonth(today.getMonth() - 3);
  
  // Use persistent state hooks
  const [tickers, setTickers] = useNodeState(id, 'tickers', 'AAPL,NVDA,TSLA');
  const [runMode, setRunMode] = useNodeState(id, 'runMode', 'single');
  const [initialCash, setInitialCash] = useNodeState(id, 'initialCash', '100000');
  const [startDate, setStartDate] = useNodeState(id, 'startDate', threeMonthsAgo.toISOString().split('T')[0]);
  const [endDate, setEndDate] = useNodeState(id, 'endDate', today.toISOString().split('T')[0]);
  const [open, setOpen] = useState(false);
  
  const { currentFlowId } = useFlowContext();
  const nodeContext = useNodeContext();
  const { getAllAgentModels } = nodeContext;
  const { getNodes, getEdges } = useReactFlow();
  const { expandBottomPanel, setBottomPanelTab } = useLayoutContext();
  
  // Use the new flow connection hook
  const flowId = currentFlowId?.toString() || null;
  const {
    isConnecting,
    isConnected,
    isProcessing,
    canRun,
    runFlow,
    runBacktest,
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
  
  // Recover flow state when component mounts or flow changes
  useEffect(() => {
    if (flowId) {
      recoverFlowState();
    }
  }, [flowId, recoverFlowState]);
  
  const handleTickersChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTickers(e.target.value);
  };

  const handleInitialCashChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Remove non-numeric characters except decimal point
    const numericValue = e.target.value.replace(/[^0-9.]/g, '');
    setInitialCash(numericValue);
  };

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setStartDate(e.target.value);
  };

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEndDate(e.target.value);
  };

  // Format the display value with commas
  const formatCurrency = (value: string) => {
    if (!value) return '';
    const num = parseFloat(value);
    if (isNaN(num)) return value;
    return num.toLocaleString('en-US');
  };

  const handleStop = () => {
    stopFlow();
  };

  const handlePlay = () => {
    // Expand bottom panel and set to output tab if backtest
    if (runMode === 'backtest') {
      expandBottomPanel();
      setBottomPanelTab('output');
    }
    
    // Get the current flow's nodes and edges
    const allNodes = getNodes();
    const allEdges = getEdges();
    
    // Find all nodes that are reachable from the stock-analyzer-node
    const reachableNodes = new Set<string>();
    const visited = new Set<string>();
    
    // DFS to find all reachable nodes
    const dfs = (nodeId: string) => {
      if (visited.has(nodeId)) return;
      visited.add(nodeId);
      
      // If this is not the stock-analyzer-node itself, add it to reachable nodes
      if (nodeId !== id) {
        reachableNodes.add(nodeId);
      }
      
      // Find all outgoing edges from this node
      const outgoingEdges = allEdges.filter(edge => edge.source === nodeId);
      for (const edge of outgoingEdges) {
        dfs(edge.target);
      }
    };
    
    // Start DFS from the stock-analyzer-node
    dfs(id);
    
    // Filter nodes to only include reachable ones
    const agentNodes = allNodes.filter(node => reachableNodes.has(node.id));
    
    // Filter edges to only include connections between reachable nodes (plus the stock-analyzer-node)
    const reachableNodeIds = new Set([id, ...reachableNodes]);
    const validEdges = allEdges.filter(edge => 
      reachableNodeIds.has(edge.source) && reachableNodeIds.has(edge.target)
    );

    // Collect agent models from all agent nodes
    const agentModels = [];
    const allAgentModels = getAllAgentModels(flowId);
    for (const node of agentNodes) {
      const model = allAgentModels[node.id];
      if (model) {
        agentModels.push({
          agent_id: node.id,
          model_name: model.model_name,
          model_provider: model.provider as any
        });
      }
    }
    
    // Convert tickers to array    
    const tickerList = tickers.split(',').map(t => t.trim());
    
    // Check if we're in backtest mode
    if (runMode === 'backtest') {
      // Use the flow connection hook to run the backtest with selected dates
      runBacktest({
        tickers: tickerList,
        // Send the actual graph structure instead of just selected agents
        graph_nodes: agentNodes.map(node => ({
          id: node.id,
          type: node.type,
          data: node.data,
          position: node.position
        })),
        graph_edges: validEdges,
        agent_models: agentModels,
        start_date: startDate,
        end_date: endDate,
        initial_capital: parseFloat(initialCash) || 100000,
        margin_requirement: 0.0, // Default margin requirement
        model_name: undefined,
        model_provider: undefined,
      });
    } else {
      // Use the regular hedge fund API for single run
      runFlow({
        tickers: tickerList,
        // Send the actual graph structure instead of just selected agents
        graph_nodes: agentNodes.map(node => ({
          id: node.id,
          type: node.type,
          data: node.data,
          position: node.position
        })),
        graph_edges: validEdges,
        agent_models: agentModels,
        // No global model - each agent uses its own model or system default
        model_name: undefined,
        model_provider: undefined,
        start_date: startDate,
        end_date: endDate,
      });
    }
  };

  // Determine if we're processing (connecting, connected, or any agents running)
  const showAsProcessing = isConnecting || isConnected || isProcessing;

  return (
    <TooltipProvider>
      <NodeShell
        id={id}
        selected={selected}
        isConnectable={isConnectable}
        icon={<ChartLine className="h-5 w-5" />}
        name={data.name || "Stock Analyzer"}
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
                <Input
                  placeholder="Enter tickers"
                  value={tickers}
                  onChange={handleTickersChange}
                />
              </div>
              <div className="flex flex-col gap-2">
                <div className="text-subtitle text-primary flex items-center gap-1">
                  Run
                </div>
                <div className="flex gap-2">
                  <Popover open={open} onOpenChange={setOpen}>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        role="combobox"
                        aria-expanded={open}
                        className="flex-1 justify-between h-10 px-3 py-2 bg-node border border-border hover:bg-accent"
                      >
                        <span className="text-subtitle">
                          {runModes.find((mode) => mode.value === runMode)?.label || 'Single Run'}
                        </span>
                        <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0 bg-node border border-border shadow-lg">
                      <Command className="bg-node">
                        <CommandList className="bg-node">
                          <CommandEmpty>No run mode found.</CommandEmpty>
                          <CommandGroup>
                            {runModes.map((mode) => (
                              <CommandItem
                                key={mode.value}
                                value={mode.value}
                                className={cn(
                                  "cursor-pointer bg-node hover:bg-accent",
                                  runMode === mode.value
                                )}
                                onSelect={(currentValue) => {
                                  setRunMode(currentValue);
                                  setOpen(false);
                                }}
                              >
                                {mode.label}
                              </CommandItem>
                            ))}
                          </CommandGroup>
                        </CommandList>
                      </Command>
                    </PopoverContent>
                  </Popover>
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
              {runMode === 'backtest' && (
                <Accordion type="single" collapsible>
                  <AccordionItem value="advanced" className="border-none">
                    <AccordionTrigger className="!text-subtitle text-primary">
                      Advanced
                    </AccordionTrigger>
                    <AccordionContent className="pt-2">
                      <div className="flex flex-col gap-4">
                        <div className="flex flex-col gap-2">
                          <div className="text-subtitle text-primary flex items-center gap-1">
                            Available Cash
                          </div>
                          <div className="relative flex-1">
                            <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground pointer-events-none">
                              $
                            </div>
                            <Input
                              type="text"
                              placeholder="100,000"
                              value={formatCurrency(initialCash)}
                              onChange={handleInitialCashChange}
                              className="pl-8 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                            />
                          </div>
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
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              )}
              {runMode === 'single' && (
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
              )}
            </div>
          </div>
        </CardContent>
      </NodeShell>
    </TooltipProvider>
  );
}
