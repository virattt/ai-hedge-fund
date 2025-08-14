import { useReactFlow, type NodeProps } from '@xyflow/react';
import { ChevronDown, PieChart, Play, Plus, Square, X } from 'lucide-react';
import { useEffect, useState } from 'react';

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
import { type PortfolioStartNode } from '../types';
import { NodeShell } from './node-shell';

interface PortfolioPosition {
  ticker: string;
  quantity: string;
  tradePrice: string;
}

const runModes = [
  { value: 'single', label: 'Single Run' },
  { value: 'backtest', label: 'Backtest' },
];

export function PortfolioStartNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<PortfolioStartNode>) {
  // Calculate default dates
  const today = new Date();
  const threeMonthsAgo = new Date(today);
  threeMonthsAgo.setMonth(today.getMonth() - 3);
  
  // Use persistent state hooks
  const [positions, setPositions] = useNodeState<PortfolioPosition[]>(id, 'positions', [
    { ticker: '', quantity: '', tradePrice: '' },
  ]);
  const [initialCash, setInitialCash] = useNodeState(id, 'initialCash', '100000');
  const [runMode, setRunMode] = useNodeState(id, 'runMode', 'single');
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
  
  // Check if the portfolio analyzer can be run
  const canRunPortfolioAnalyzer = canRun && positions.length > 0 && positions.every(pos => pos.ticker.trim() !== '');
  
  // Add keyboard shortcut for Cmd+Enter / Ctrl+Enter to run portfolio analyzer
  useKeyboardShortcuts({
    shortcuts: [
      {
        key: 'Enter',
        ctrlKey: true,
        metaKey: true,
        callback: () => {
          if (canRunPortfolioAnalyzer) {
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
  
  const handlePositionChange = (index: number, field: keyof PortfolioPosition, value: string) => {
    const newPositions = [...positions];
    newPositions[index][field] = value;
    setPositions(newPositions);
  };

  const addPosition = () => {
    setPositions([...positions, { ticker: '', quantity: '', tradePrice: '' }]);
  };

  const removePosition = (index: number) => {
    const newPositions = positions.filter((_, i) => i !== index);
    setPositions(newPositions);
  };

  const handleInitialCashChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInitialCash(e.target.value);
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
    // Expand bottom panel and set to output tab if backtest
    if (runMode === 'backtest') {
      expandBottomPanel();
      setBottomPanelTab('output');
    }
    
    // Get the current flow's nodes and edges
    const allNodes = getNodes();
    const allEdges = getEdges();
    
    // Find all nodes that are reachable from the portfolio-analyzer-node
    const reachableNodes = new Set<string>();
    const visited = new Set<string>();
    
    // DFS to find all reachable nodes
    const dfs = (nodeId: string) => {
      if (visited.has(nodeId)) return;
      visited.add(nodeId);
      
      // If this is not the portfolio-analyzer-node itself, add it to reachable nodes
      if (nodeId !== id) {
        reachableNodes.add(nodeId);
      }
      
      // Find all outgoing edges from this node
      const outgoingEdges = allEdges.filter(edge => edge.source === nodeId);
      for (const edge of outgoingEdges) {
        dfs(edge.target);
      }
    };
    
    // Start DFS from the portfolio-analyzer-node
    dfs(id);
    
    // Filter nodes to only include reachable ones
    const agentNodes = allNodes.filter(node => reachableNodes.has(node.id));
    
    // Filter edges to only include connections between reachable nodes (plus the portfolio-analyzer-node)
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
    
    // Convert positions to the expected format for backend use
    const portfolioPositions = positions
      .filter(pos => pos.ticker.trim() !== '' && pos.quantity.trim() !== '' && pos.tradePrice.trim() !== '')
      .map(pos => ({
        ticker: pos.ticker.trim(),
        quantity: parseFloat(pos.quantity) || 0,
        trade_price: parseFloat(pos.tradePrice) || 0
      }));
    
    // For now, extract tickers for current API compatibility
    const tickerList = positions.map(pos => pos.ticker.trim()).filter(ticker => ticker !== '');
    
    // Check if we're in backtest mode
    if (runMode === 'backtest') {
      // Use the flow connection hook to run the backtest with selected dates
      runBacktest({
        tickers: tickerList,
        // Send the actual graph structure instead of just selected analysts
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
        // Pass portfolio positions to backend
        portfolio_positions: portfolioPositions,
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
        start_date: threeMonthsAgo.toISOString().split('T')[0],
        end_date: today.toISOString().split('T')[0],
        initial_cash: parseFloat(initialCash) || 100000,
        // Pass portfolio positions to backend
        portfolio_positions: portfolioPositions,
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
        icon={<PieChart className="h-5 w-5" />}
        name={data.name || "Portfolio Analyzer"}
        description={data.description}
        hasLeftHandle={false}
        width="w-80"
      >
        <CardContent className="p-0">
          <div className="border-t border-border p-3">
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
                    type="number"
                    placeholder="100000"
                    value={initialCash}
                    onChange={handleInitialCashChange}
                    className="pl-8 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    step="0.01"
                    min="0"
                  />
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <div className="text-subtitle text-primary flex items-center gap-1">
                  <Tooltip delayDuration={200}>
                    <TooltipTrigger asChild>
                      <span>Positions</span>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      Add your portfolio positions with ticker, quantity, and trade price
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="flex flex-col gap-2">
                  {positions.map((position, index) => {
                    return (
                    <div key={index} className="flex gap-2 items-center">
                      <Input
                        placeholder="Ticker"
                        value={position.ticker}
                        onChange={(e) => handlePositionChange(index, 'ticker', e.target.value)}
                        className="flex-1"
                      />
                      <Input
                        type="number"
                        placeholder="Quantity"
                        value={position.quantity}
                        onChange={(e) => handlePositionChange(index, 'quantity', e.target.value)}
                        className="w-20"
                        step="any"
                      />
                      <div className="relative flex-1">
                        <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground pointer-events-none">
                          $
                        </div>
                        <Input
                          type="number"
                          placeholder="Price"
                          value={position.tradePrice}
                          onChange={(e) => handlePositionChange(index, 'tradePrice', e.target.value)}
                          className="pl-8"
                          step="0.01"
                          min="0"
                        />
                      </div>
                      {positions.length > 1 && (
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => removePosition(index)}
                          className="flex-shrink-0 h-8 w-4 text-muted-foreground hover:text-destructive"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                    );
                  })}
                  <Button
                    onClick={addPosition}
                    className="w-full mt-2 transition-all duration-200 hover:bg-primary hover:text-primary-foreground active:scale-95"
                    size="sm"
                    variant="secondary"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add Position
                  </Button>
                </div>
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
                          {runModes.find((mode) => mode.value === runMode)?.label || 'Single Analysis'}
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
                    disabled={!canRunPortfolioAnalyzer && !showAsProcessing}
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
                <div className="flex flex-col gap-4">
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
              )}
            </div>
          </div>
        </CardContent>
      </NodeShell>
    </TooltipProvider>
  );
}
