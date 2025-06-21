import { type NodeProps } from '@xyflow/react';
import { FileText, Loader2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { CardContent } from '@/components/ui/card';
import { useNodeContext } from '@/contexts/node-context';
import { type InvestmentReportNode } from '../types';
import { InvestmentReportDialog } from './investment-report-dialog';
import { NodeShell } from './node-shell';

export function InvestmentReportNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<InvestmentReportNode>) {  
  const { outputNodeData, agentNodeData } = useNodeContext();
  const [showOutput, setShowOutput] = useState(false);
  
  // Check if any agent is in progress
  const isProcessing = Object.values(agentNodeData).some(
    agent => agent.status === 'IN_PROGRESS'
  );
  
  const isOutputAvailable = !!outputNodeData;

  const handleViewOutput = () => {
    setShowOutput(true);
  }

  return (
    <>
      <NodeShell
        id={id}
        selected={selected}
        isConnectable={isConnectable}
        icon={<FileText className="h-5 w-5" />}
        name={data.name || "Investment Report"}
        description={data.description}
        hasRightHandle={false}
      >
        <CardContent className="p-0">
          <div className="border-t border-border p-3">
            <div className="flex flex-col gap-2">
              <div className="text-subtitle text-muted-foreground flex items-center gap-1">
                Results
              </div>
              <div className="flex gap-2">
                {isProcessing ? (
                  <Button 
                    variant="secondary"
                    className="w-full flex-shrink-0 transition-all duration-200 hover:bg-primary hover:text-primary-foreground active:scale-95 text-subtitle"
                    disabled
                  >
                    <Loader2 className="h-2 w-2 animate-spin" />
                    Processing...
                  </Button>
                ) : (
                  <Button 
                    variant="secondary"
                    className="w-full flex-shrink-0 transition-all duration-200 hover:bg-primary hover:text-primary-foreground active:scale-95 text-subtitle"
                    onClick={handleViewOutput}
                    disabled={!isOutputAvailable}
                  >
                   View Output
                  </Button>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </NodeShell>
      <InvestmentReportDialog 
        isOpen={showOutput} 
        onOpenChange={setShowOutput} 
        outputNodeData={outputNodeData} 
      />
    </>
  );
}
