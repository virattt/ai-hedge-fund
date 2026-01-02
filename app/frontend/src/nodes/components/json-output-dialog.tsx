import { Copy, Download } from 'lucide-react';
import { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';

interface JsonOutputDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  outputNodeData: any;
  connectedAgentIds: Set<string>;
}

export function JsonOutputDialog({ 
  isOpen, 
  onOpenChange, 
  outputNodeData,
  connectedAgentIds
}: JsonOutputDialogProps) {
  const [copySuccess, setCopySuccess] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  if (!outputNodeData) return null;

  // Convert React Flow node IDs to backend agent keys for filtering
  const connectedBackendAgentKeys = Array.from(connectedAgentIds).map(nodeId => `${nodeId}_agent`);
  
  // Filter the outputNodeData to only include connected agents
  const filteredOutputData = {
    ...outputNodeData,
    analyst_signals: Object.fromEntries(
      Object.entries(outputNodeData.analyst_signals || {})
        .filter(([agentId]) => 
          agentId === 'risk_management_agent' || connectedBackendAgentKeys.includes(agentId)
        )
    )
  };

  const jsonString = JSON.stringify(filteredOutputData, null, 2);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(jsonString)
      .then(() => {
        setCopySuccess(true);
        setTimeout(() => setCopySuccess(false), 2000);
      })
      .catch(err => {
        console.error('Failed to copy text: ', err);
      });
  };

  const downloadJson = () => {
    try {
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `output-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
      setDownloadSuccess(true);
      setTimeout(() => setDownloadSuccess(false), 2000);
    } catch (err) {
      console.error('Failed to download JSON: ', err);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold flex items-center justify-between">
            JSON Output
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={copyToClipboard}
                className="flex items-center gap-1.5"
              >
                <Copy className="h-4 w-4" />
                <span className="font-medium">{copySuccess ? 'Copied!' : 'Copy'}</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={downloadJson}
                className="flex items-center gap-1.5"
              >
                <Download className="h-4 w-4" />
                <span className="font-medium">{downloadSuccess ? 'Downloaded!' : 'Download'}</span>
              </Button>
            </div>
          </DialogTitle>
        </DialogHeader>
        
        <div className="flex-1 min-h-0 my-4 overflow-auto rounded-md border border-border bg-muted/30">
          <SyntaxHighlighter
            language="json"
            style={vscDarkPlus}
            customStyle={{
              margin: 0,
              padding: '0.75rem',
              fontSize: '0.875rem',
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              wordWrap: 'break-word',
              overflowWrap: 'break-word',
            }}
            wrapLines={true}
            wrapLongLines={true}
          >
            {jsonString}
          </SyntaxHighlighter>
        </div>
      </DialogContent>
    </Dialog>
  );
} 