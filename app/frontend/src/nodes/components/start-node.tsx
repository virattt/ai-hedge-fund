import { useReactFlow, type NodeProps } from '@xyflow/react';
import { Bot, Play } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useNodeStatus } from '@/contexts/node-status-context';
import { api } from '@/services/api';
import { type StartNode } from '../types';
import { getStatusColor } from '../utils';
import { NodeShell } from './node-shell';

export function StartNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<StartNode>) {
  const [tickers, setTickers] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const nodeStatusContext = useNodeStatus();
  const { resetAllStatuses, nodeStates, updateNodeStatus } = nodeStatusContext;
  const { getNodes } = useReactFlow();
  const status = nodeStates[id] || 'IDLE';
  const abortControllerRef = useRef<(() => void) | null>(null);
  
  // Clean up SSE connection on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current();
      }
    };
  }, []);
  
  const handleTickersChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTickers(e.target.value);
  };

  const handlePlay = () => {
    setIsProcessing(true);
    
    // First, reset all nodes to IDLE
    resetAllStatuses();
    
    // Update this node to IN_PROGRESS
    updateNodeStatus(id, 'IN_PROGRESS');
    
    // Clean up any existing connection
    if (abortControllerRef.current) {
      abortControllerRef.current();
    }
    
    // Call the backend API with SSE
    const tickerList = tickers.split(',').map(t => t.trim());
    
    // Get the select agents from the context and filter out the start node and portfolio_manager
    const selectedAgents = getNodes()
      .map(node => node.id as string)
      .filter(Boolean);
    
    abortControllerRef.current = api.runHedgeFund(
      {
        tickers: tickerList,
        selected_agents: selectedAgents,
      },
      (event) => {
        // Basic status updates for start node only (agent-specific updates are handled by the API)
        if (event.type === 'complete') {
          setIsProcessing(false);
          updateNodeStatus(id, 'COMPLETE');
        } 
        else if (event.type === 'error') {
          setIsProcessing(false);
          updateNodeStatus(id, 'ERROR');
        }
      },
      // Pass the node status context to the API
      nodeStatusContext
    );
  };

  return (
    <NodeShell
      id={id}
      selected={selected}
      isConnectable={isConnectable}
      icon={<Bot className="h-5 w-5" />}
      iconColor={getStatusColor(status)}
      name={data.name || "Custom Component"}
      description={data.description}
      hasLeftHandle={false}
    >
      <CardContent className="p-0">
        <div className="border-t border-border p-3">
          <div className="flex flex-col gap-2">
            <div className="text-subtitle text-muted-foreground flex items-center gap-1">
              Tickers
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
                onClick={handlePlay}
                disabled={isProcessing || !tickers.trim()}
              >
                <Play className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
        <div className="border-t border-border p-3 flex justify-end items-center">
          <div className="flex items-center gap-1">
            <div className="text-subtitle text-muted-foreground">Output</div>
            <div className="text-subtitle text-muted-foreground">≡</div>
          </div>
        </div>
      </CardContent>
    </NodeShell>
  );
}
