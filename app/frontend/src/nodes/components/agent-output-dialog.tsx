import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { useNodeContext } from '@/contexts/node-context';
import { formatTimeFromTimestamp } from '@/utils/date-utils';
import { formatContent } from '@/utils/text-utils';
import { AlignJustify, Copy, Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface AgentOutputDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  nodeId: string;
}

export function AgentOutputDialog({ 
  isOpen, 
  onOpenChange, 
  name, 
  nodeId 
}: AgentOutputDialogProps) {
  const { agentNodeData } = useNodeContext();
  const nodeData = agentNodeData[nodeId] || { 
    status: 'IDLE', 
    ticker: null, 
    message: '', 
    messages: [],
    lastUpdated: 0
  };
  const messages = nodeData.messages || [];
  const nodeStatus = nodeData.status;
  
  const [copySuccess, setCopySuccess] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const initialFocusRef = useRef<HTMLDivElement>(null);

  // Collect all analysis from all messages into a single analysis dictionary
  const allAnalysis = messages.reduce<Record<string, string>>((acc, msg) => {
    // Add analysis from this message to our accumulated analysis
    if (msg.analysis && Object.keys(msg.analysis).length > 0) {
      // Filter out null values before adding to our accumulated decisions
      const validDecisions = Object.entries(msg.analysis)
        .filter(([_, value]) => value !== null && value !== undefined)
        .reduce((obj, [key, value]) => {
          obj[key] = value;
          return obj;
        }, {} as Record<string, string>);
      
      if (Object.keys(validDecisions).length > 0) {
        // Combine with accumulated decisions, newer messages overwrite older ones for the same ticker
        return { ...acc, ...validDecisions };
      }
    }
    return acc;
  }, {});

  // Get all unique tickers that have decisions
  const tickersWithDecisions = Object.keys(allAnalysis);

  // Reset selected ticker when node changes
  useEffect(() => {
    setSelectedTicker(null);
  }, [nodeId]);

  // If no ticker is selected but we have decisions, select the first one
  useEffect(() => {
    if (tickersWithDecisions.length > 0 && (!selectedTicker || !tickersWithDecisions.includes(selectedTicker))) {
      setSelectedTicker(tickersWithDecisions[0]);
    }
  }, [tickersWithDecisions, selectedTicker]);

  // Get the selected decision text
  const selectedDecision = selectedTicker && allAnalysis[selectedTicker] ? allAnalysis[selectedTicker] : null;

  const copyToClipboard = () => {
    if (selectedDecision) {
      navigator.clipboard.writeText(selectedDecision)
        .then(() => {
          setCopySuccess(true);
          setTimeout(() => setCopySuccess(false), 2000);
        })
        .catch(err => {
          console.error('Failed to copy text: ', err);
        });
    }
  };

  return (
    <Dialog 
      open={isOpen} 
      onOpenChange={onOpenChange}
      defaultOpen={false}
      modal={true}
    >
      <DialogTrigger asChild>
        <div className="border-t border-border p-3 flex justify-end items-center cursor-pointer hover:bg-accent/50" onClick={() => onOpenChange(true)}>
          <div className="flex items-center gap-1">
            <div className="text-subtitle text-muted-foreground">Output</div>
            <AlignJustify className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
        </div>
      </DialogTrigger>
      <DialogContent 
        className="sm:max-w-[900px]" 
        autoFocus={false} 
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{name}</DialogTitle>
        </DialogHeader>
        
        <div className="grid grid-cols-2 gap-6 pt-4" ref={initialFocusRef} tabIndex={-1}>
          {/* Activity Log Section */}
          <div>
            <h3 className="font-medium mb-3 text-primary">Log</h3>
            <div className="h-[400px] overflow-y-auto border border-border rounded-lg p-3">
              {messages.length > 0 ? (
                <div className="p-3 space-y-3">
                  {[...messages].reverse().map((msg, idx) => (
                    <div key={idx} className="border-l-2 border-primary pl-3 text-sm">
                      <div className="text-foreground">
                        {msg.ticker && <span>[{msg.ticker}] </span>}
                        {msg.message}
                      </div>
                      <div className="text-muted-foreground">
                        {formatTimeFromTimestamp(msg.timestamp)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  No activity available
                </div>
              )}
            </div>
          </div>
          
          {/* Analysis Section */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-medium text-primary">Analysis</h3>
              <div className="flex items-center gap-2">
                {/* Ticker selector */}
                {tickersWithDecisions.length > 0 && (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-muted-foreground font-medium">Ticker:</span>
                    <select 
                      className="text-xs p-1 rounded bg-background border border-border cursor-pointer"
                      value={selectedTicker || ''}
                      onChange={(e) => setSelectedTicker(e.target.value)}
                      autoFocus={false}
                    >
                      {tickersWithDecisions.map((ticker) => (
                        <option key={ticker} value={ticker}>
                          {ticker}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>
            <div className="h-[400px] overflow-y-auto border border-border rounded-lg p-3">
              {tickersWithDecisions.length > 0 ? (
                <div className="p-3 rounded-lg text-sm leading-relaxed">
                  {selectedTicker && (
                    <div className="mb-3 flex justify-between items-center">
                      <div className=" text-muted-foreground font-medium">Summary for {selectedTicker}</div>
                      {selectedDecision && (
                        <button 
                          onClick={copyToClipboard}
                          className="flex items-center gap-1.5 text-xs p-1.5 rounded hover:bg-accent transition-colors text-muted-foreground"
                          title="Copy to clipboard"
                        >
                          <Copy className="h-3.5 w-3.5 " />
                          <span className="font-medium">{copySuccess ? 'Copied!' : 'Copy'}</span>
                        </button>
                      )}
                    </div>
                  )}
                  {selectedDecision ? (
                    (() => {
                      const { isJson, formattedContent } = formatContent(selectedDecision);
                      
                      if (isJson) {
                        // Use react-syntax-highlighter for better JSON rendering
                        return (
                          <div className="overflow-auto rounded-md text-xs">
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
                              showLineNumbers={false}
                              wrapLines={true}
                              wrapLongLines={true}
                            >
                              {formattedContent as string}
                            </SyntaxHighlighter>
                          </div>
                        );
                      } else {
                        // Display as regular text paragraphs
                        return (
                          (formattedContent as string[]).map((paragraph, idx) => (
                            <p key={idx} className="mb-3 last:mb-0">{paragraph}</p>
                          ))
                        );
                      }
                    })()
                  ) : nodeStatus === 'IN_PROGRESS' ? (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      <Loader2 className="h-5 w-5 animate-spin mr-2" />
                      Analysis in progress...
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      No analysis available for {selectedTicker}
                    </div>
                  )}
                </div>
              ) : nodeStatus === 'IN_PROGRESS' ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin mr-2" />
                  Analysis in progress...
                </div>
              ) : nodeStatus === 'COMPLETE' ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Analysis completed with no results
                </div>
              ) : nodeStatus === 'ERROR' ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Analysis failed
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  No analysis available
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
} 