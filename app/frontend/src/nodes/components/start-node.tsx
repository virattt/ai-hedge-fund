import { type NodeProps } from '@xyflow/react';
import { Bot, Play } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useState } from 'react';
import { type StartNode } from '../types';
import { NodeShell } from './node-shell';

export function StartNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<StartNode>) {
  const [tickers, setTickers] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleTickersChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTickers(e.target.value);
  };

  const handlePlay = () => {
    setIsProcessing(true);
    // Simulate processing
    setTimeout(() => {
      setIsProcessing(false);
    }, 1000);
  };

  return (
    <NodeShell
      id={id}
      selected={selected}
      isConnectable={isConnectable}
      icon={<Bot className="h-5 w-5" />}
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
