import { type NodeProps } from '@xyflow/react';
import { FileJson } from 'lucide-react';
import { useEffect, useState } from 'react';

import { CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { useFlowContext } from '@/contexts/flow-context';
import { useNodeContext } from '@/contexts/node-context';
import { useOutputNodeConnection } from '@/hooks/use-output-node-connection';
import { api } from '@/services/api';
import { type JsonOutputNode } from '../types';
import { JsonOutputDialog } from './json-output-dialog';
import { NodeShell } from './node-shell';
import { OutputNodeStatus } from './output-node-status';

export function JsonOutputNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<JsonOutputNode>) {  
  const { currentFlowId } = useFlowContext();
  const { getOutputNodeDataForFlow } = useNodeContext();
  
  // Get output node data for the current flow
  const flowId = currentFlowId?.toString() || null;
  const outputNodeData = getOutputNodeDataForFlow(flowId);
  
  const [showOutput, setShowOutput] = useState(false);
  const [saveToFile, setSaveToFile] = useState(false);
  
  // Use the custom hook for connection logic
  const { isProcessing, isAnyAgentRunning, isOutputAvailable, isConnected, connectedAgentIds } = useOutputNodeConnection(id);
  const status = isProcessing || isAnyAgentRunning ? 'IN_PROGRESS' : 'IDLE';

  // Save to file when output is available and saveToFile is enabled
  useEffect(() => {
    if (saveToFile && isOutputAvailable && outputNodeData) {
      saveJsonFile(outputNodeData);
    }
  }, [saveToFile, isOutputAvailable, outputNodeData]);

  const saveJsonFile = async (data: any) => {
    try {
      // Generate filename with current date and time in user's timezone
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const seconds = String(now.getSeconds()).padStart(2, '0');
      const dateTime = `${year}-${month}-${day}_${hours}h${minutes}m${seconds}s`;
      const filename = `run_${dateTime}.json`;

      // Save file via API
      await api.saveJsonFile(filename, data);
      
      console.log(`JSON output saved to outputs/${filename}`);
    } catch (error) {
      console.error('Failed to save JSON output:', error);
    }
  };

  const handleViewOutput = () => {
    setShowOutput(true);
  }

  return (
    <>
      <NodeShell
        id={id}
        selected={selected}
        isConnectable={isConnectable}
        icon={<FileJson className="h-5 w-5" />}
        name={data.name || "JSON Output"}
        description={data.description}
        hasRightHandle={false}
        status={status}
      >
        <CardContent className="p-0">
          <div className="border-t border-border p-3">
            <div className="flex flex-col gap-2">
              <div className="text-subtitle text-muted-foreground flex items-center gap-1">
                Results
              </div>
              
              <OutputNodeStatus
                isProcessing={isProcessing}
                isAnyAgentRunning={isAnyAgentRunning}
                isOutputAvailable={isOutputAvailable}
                isConnected={isConnected}
                onViewOutput={handleViewOutput}
              />
              
              <div className="flex items-center space-x-2 mt-2">
                <Checkbox
                  id="save-to-file"
                  checked={saveToFile}
                  onCheckedChange={(checked: boolean) => setSaveToFile(checked)}
                />
                <label
                  htmlFor="save-to-file"
                  className="text-subtitle text-muted-foreground cursor-pointer"
                >
                  Save to File
                </label>
              </div>
            </div>
          </div>
        </CardContent>
      </NodeShell>

      <JsonOutputDialog 
        isOpen={showOutput} 
        onOpenChange={setShowOutput} 
        outputNodeData={outputNodeData} 
        connectedAgentIds={connectedAgentIds}
      />
    </>
  );
} 