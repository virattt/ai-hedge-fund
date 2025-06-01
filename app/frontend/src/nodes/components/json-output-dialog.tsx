import { Copy, Download } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { createHighlightedJson, formatContent } from '@/utils/text-utils';

interface JsonOutputDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  outputNodeData: any;
}

export function JsonOutputDialog({ 
  isOpen, 
  onOpenChange, 
  outputNodeData 
}: JsonOutputDialogProps) {
  const [copySuccess, setCopySuccess] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  if (!outputNodeData) return null;

  const jsonString = JSON.stringify(outputNodeData, null, 2);

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

  // Format the output data as JSON
  const { isJson, formattedContent } = formatContent(jsonString);
  
  // Use our custom JSON highlighter
  const highlightedJson = createHighlightedJson(formattedContent as string);

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
        
        <div className="flex-1 min-h-0 my-4">
          <div className="h-full rounded-md border border-border overflow-auto bg-muted/30">
            <div className="p-4 w-full">
              <pre 
                className="whitespace-pre text-sm w-full"
                style={{ 
                  fontFamily: 'monospace',
                  lineHeight: 1.5,
                  color: '#d4d4d4',
                  margin: 0,
                  minWidth: 'max-content',
                }}
              >
                <code dangerouslySetInnerHTML={{ __html: highlightedJson }} />
              </pre>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
} 