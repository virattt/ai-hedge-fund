import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';
import { getActionColor, getDisplayName, getSignalColor, getStatusIcon } from './output-tab-utils';
import { ReasoningContent } from './reasoning-content';

// Progress Section Component
function ProgressSection({ sortedAgents }: { sortedAgents: [string, any][] }) {
  if (sortedAgents.length === 0) return null;

  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">Progress</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {sortedAgents.map(([agentId, data]) => {
            const { icon: StatusIcon, color } = getStatusIcon(data.status);
            const displayName = getDisplayName(agentId);
            
            return (
              <div key={agentId} className="flex items-center gap-2">
                <StatusIcon className={cn("h-4 w-4 flex-shrink-0", color)} />
                <span className="font-medium">{displayName}</span>
                {data.ticker && (
                  <span>[{data.ticker}]</span>
                )}
                <span className={cn("flex-1", color)}>
                  {data.message || data.status}
                </span>
                {data.timestamp && (
                  <span className="text-muted-foreground text-xs">
                    {new Date(data.timestamp).toLocaleTimeString()}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

// Summary Section Component
function SummarySection({ outputData }: { outputData: any }) {
  if (!outputData) return null;

  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ticker</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Quantity</TableHead>
              <TableHead>Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(outputData.decisions).map(([ticker, decision]: [string, any]) => (
              <TableRow key={ticker}>
                <TableCell className="font-medium">{ticker}</TableCell>
                <TableCell>
                  <span className={cn("font-medium", getActionColor(decision.action || ''))}>
                    {decision.action?.toUpperCase() || 'UNKNOWN'}
                  </span>
                </TableCell>
                <TableCell>{decision.quantity || 0}</TableCell>
                <TableCell>{decision.confidence?.toFixed(1) || 0}%</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// Analysis Results Section Component
function AnalysisResultsSection({ outputData }: { outputData: any }) {
  // Always call hooks at the top of the function
  const [selectedTicker, setSelectedTicker] = useState<string>('');
  
  // Calculate tickers (safe to do even if outputData is null)
  const tickers = outputData?.decisions ? Object.keys(outputData.decisions) : [];
  
  // Set default selected ticker
  useEffect(() => {
    if (tickers.length > 0 && !selectedTicker) {
      setSelectedTicker(tickers[0]);
    }
  }, [tickers, selectedTicker]);

  // Early returns after all hooks are called
  if (!outputData) return null;
  if (tickers.length === 0) return null;

  return (
    <Card className="bg-transparent">
      <CardHeader>
        <CardTitle className="text-lg">Analysis</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={selectedTicker} onValueChange={setSelectedTicker} className="w-full">
          <TabsList className="flex space-x-1 bg-muted p-1 rounded-lg mb-4">
            {tickers.map((ticker) => (
              <TabsTrigger 
                key={ticker} 
                value={ticker} 
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-colors data-[state=active]:active-bg data-[state=active]:text-blue-500 data-[state=active]:shadow-sm text-primary hover:text-primary hover-bg"
              >
                {ticker}
              </TabsTrigger>
            ))}
          </TabsList>
          
          {tickers.map((ticker) => {
            const decision = outputData.decisions![ticker];
            
            return (
              <TabsContent key={ticker} value={ticker} className="space-y-4">
                {/* Agent Analysis */}
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Agent</TableHead>
                      <TableHead>Signal</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Reasoning</TableHead>
                    </TableRow>
                  </TableHeader>
                                     <TableBody>
                     {Object.entries(outputData.analyst_signals || {})
                       .filter(([agent, signals]: [string, any]) => 
                         ticker in signals && !agent.includes("risk_management")
                       )
                       .sort(([agentA], [agentB]) => agentA.localeCompare(agentB))
                       .map(([agent, signals]: [string, any]) => {
                         const signal = signals[ticker];
                         const signalType = signal.signal?.toUpperCase() || 'UNKNOWN';
                         const signalColor = getSignalColor(signalType);
                        
                        return (
                          <TableRow key={agent}>
                            <TableCell className="font-medium">
                              {getDisplayName(agent)}
                            </TableCell>
                            <TableCell>
                              <span className={cn("font-medium", signalColor)}>
                                {signalType}
                              </span>
                            </TableCell>
                            <TableCell>{signal.confidence || 0}%</TableCell>
                            <TableCell className="max-w-md">
                              <ReasoningContent content={signal.reasoning} />
                            </TableCell>
                          </TableRow>
                        );
                      })}
                  </TableBody>
                </Table>
                
                {/* Trading Decision */}
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Property</TableHead>
                      <TableHead>Value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell className="font-medium">Action</TableCell>
                      <TableCell>
                        <span className={cn("font-medium", getActionColor(decision.action || ''))}>
                          {decision.action?.toUpperCase() || 'UNKNOWN'}
                        </span>
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium">Quantity</TableCell>
                      <TableCell>{decision.quantity || 0}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium">Confidence</TableCell>
                      <TableCell>{decision.confidence?.toFixed(1) || 0}%</TableCell>
                    </TableRow>
                    {decision.reasoning && (
                      <TableRow>
                        <TableCell className="font-medium">Reasoning</TableCell>
                        <TableCell className="max-w-md">
                          <ReasoningContent content={decision.reasoning} />
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TabsContent>
            );
          })}
        </Tabs>
      </CardContent>
    </Card>
  );
}

// Main component for regular output
export function RegularOutput({ 
  sortedAgents, 
  outputData 
}: { 
  sortedAgents: [string, any][]; 
  outputData: any; 
}) {
  return (
    <>
      <ProgressSection sortedAgents={sortedAgents} />
      <SummarySection outputData={outputData} />
      <AnalysisResultsSection outputData={outputData} />
    </>
  );
} 