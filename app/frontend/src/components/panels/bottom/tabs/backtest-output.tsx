import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { MoreHorizontal } from 'lucide-react';
import { getActionColor } from './output-tab-utils';

// Component for displaying backtest progress
function BacktestProgress({ agentData }: { agentData: Record<string, any> }) {
  const backtestAgent = agentData['backtest'];
  
  if (!backtestAgent) return null;
  
  // Get the latest backtest result from the backtest results array
  const backtestResults = backtestAgent.backtestResults || [];
  const latestBacktestResult = backtestResults.length > 0 ? backtestResults[backtestResults.length - 1] : null;
  
  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">Backtest Progress</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Current Status */}
          <div className="flex items-center gap-2">
            <MoreHorizontal className="h-4 w-4 text-yellow-500" />
            <span className="font-medium">Backtest Runner</span>
            <span className="text-yellow-500 flex-1">{backtestAgent.message || backtestAgent.status}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Component for displaying backtest trading table (similar to CLI)
function BacktestTradingTable({ agentData }: { agentData: Record<string, any> }) {
  const backtestAgent = agentData['backtest'];

  // console.log("backtestAgent", backtestAgent);
  
  if (!backtestAgent || !backtestAgent.backtestResults) {
    return null;
  }
    
  // Get the backtest results directly from the agent data
  const backtestResults = backtestAgent.backtestResults || [];
  
  if (backtestResults.length === 0) {
    return null;
  }
  
  // Build table rows similar to CLI format
  const tableRows: any[] = [];
  
  backtestResults.forEach((backtestResult: any) => {    
    // Add ticker rows for this period
    if (backtestResult.ticker_details) {
      backtestResult.ticker_details.forEach((ticker: any) => {
        tableRows.push({
          type: 'ticker',
          date: backtestResult.date,
          ticker: ticker.ticker,
          action: ticker.action,
          quantity: ticker.quantity,
          price: ticker.price,
          shares_owned: ticker.shares_owned,
          long_shares: ticker.long_shares,
          short_shares: ticker.short_shares,
          position_value: ticker.position_value,
          bullish_count: ticker.bullish_count,
          bearish_count: ticker.bearish_count,
          neutral_count: ticker.neutral_count,
        });
      });
    }
    
    // Add portfolio summary row for this period
    tableRows.push({
      type: 'summary',
      date: backtestResult.date,
      portfolio_value: backtestResult.portfolio_value,
      cash: backtestResult.cash,
      portfolio_return: backtestResult.portfolio_return,
      total_position_value: backtestResult.portfolio_value - backtestResult.cash,
      performance_metrics: backtestResult.performance_metrics,
    });
  });
    
  // Sort by date descending (newest first) and show only the last 50 rows to avoid performance issues
  const recentRows = tableRows
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 50);
  
  
  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="max-h-96 overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Ticker</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Quantity</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Shares</TableHead>
                <TableHead>Position Value</TableHead>
                <TableHead>Bullish</TableHead>
                <TableHead>Bearish</TableHead>
                <TableHead>Neutral</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentRows.map((row: any, idx: number) => {
                if (row.type === 'ticker') {
                  return (
                    <TableRow key={idx}>
                      <TableCell className="font-medium">{row.date}</TableCell>
                      <TableCell className="font-medium text-cyan-500">{row.ticker}</TableCell>
                      <TableCell>
                        <span className={cn("font-medium", getActionColor(row.action || ''))}>
                          {row.action?.toUpperCase() || 'HOLD'}
                        </span>
                      </TableCell>
                      <TableCell className={cn("font-medium", getActionColor(row.action || ''))}>
                        {row.quantity?.toLocaleString() || 0}
                      </TableCell>
                      <TableCell>${row.price?.toFixed(2) || '0.00'}</TableCell>
                      <TableCell>{row.shares_owned?.toLocaleString() || 0}</TableCell>
                      <TableCell className="text-primary">
                        ${row.position_value?.toLocaleString() || '0'}
                      </TableCell>
                      <TableCell className="text-green-500">{row.bullish_count || 0}</TableCell>
                      <TableCell className="text-red-500">{row.bearish_count || 0}</TableCell>
                      <TableCell className="text-blue-500">{row.neutral_count || 0}</TableCell>
                    </TableRow>
                  );
                }
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

// Component for displaying backtest results
function BacktestResults({ outputData }: { outputData: any }) {
  if (!outputData) {
    return null;
  }

  console.log("outputData", outputData);
  
  if (!outputData.performance_metrics) {
    return (
      <Card className="bg-transparent mb-4">
        <CardHeader>
          <CardTitle className="text-lg">Backtest Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            Backtest completed. Performance metrics will appear here.
          </div>
        </CardContent>
      </Card>
    );
  }
  
  const { performance_metrics, final_portfolio, total_days } = outputData;
  
  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">Backtest Results</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {/* Performance Metrics */}
          <div className="space-y-2">
            <h4 className="font-medium">Performance Metrics</h4>
            <div className="space-y-1 text-sm">
              {performance_metrics.sharpe_ratio !== null && performance_metrics.sharpe_ratio !== undefined && (
                <div className="flex justify-between">
                  <span>Sharpe Ratio:</span>
                  <span className={cn("font-medium", performance_metrics.sharpe_ratio > 1 ? "text-green-500" : "text-red-500")}>
                    {performance_metrics.sharpe_ratio.toFixed(2)}
                  </span>
                </div>
              )}
              {performance_metrics.sortino_ratio !== null && performance_metrics.sortino_ratio !== undefined && (
                <div className="flex justify-between">
                  <span>Sortino Ratio:</span>
                  <span className={cn("font-medium", performance_metrics.sortino_ratio > 1 ? "text-green-500" : "text-red-500")}>
                    {performance_metrics.sortino_ratio.toFixed(2)}
                  </span>
                </div>
              )}
              {performance_metrics.max_drawdown !== null && performance_metrics.max_drawdown !== undefined && (
                <div className="flex justify-between">
                  <span>Max Drawdown:</span>
                  <span className="font-medium text-red-500">
                    {Math.abs(performance_metrics.max_drawdown).toFixed(2)}%
                  </span>
                </div>
              )}
            </div>
          </div>
          
          {/* Portfolio Summary */}
          <div className="space-y-2">
            <h4 className="font-medium">Portfolio Summary</h4>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span>Total Days:</span>
                <span className="font-medium">{total_days}</span>
              </div>
              <div className="flex justify-between">
                <span>Final Cash:</span>
                <span className="font-medium">${final_portfolio.cash.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span>Margin Used:</span>
                <span className="font-medium">${final_portfolio.margin_used.toLocaleString()}</span>
              </div>
            </div>
          </div>
          
          {/* Exposure Metrics */}
          <div className="space-y-2">
            <h4 className="font-medium">Exposure Metrics</h4>
            <div className="space-y-1 text-sm">
              {performance_metrics.gross_exposure !== null && performance_metrics.gross_exposure !== undefined && (
                <div className="flex justify-between">
                  <span>Gross Exposure:</span>
                  <span className="font-medium">${performance_metrics.gross_exposure.toLocaleString()}</span>
                </div>
              )}
              {performance_metrics.net_exposure !== null && performance_metrics.net_exposure !== undefined && (
                <div className="flex justify-between">
                  <span>Net Exposure:</span>
                  <span className="font-medium">${performance_metrics.net_exposure.toLocaleString()}</span>
                </div>
              )}
              {performance_metrics.long_short_ratio !== null && performance_metrics.long_short_ratio !== undefined && (
                <div className="flex justify-between">
                  <span>Long/Short Ratio:</span>
                  <span className="font-medium">
                    {performance_metrics.long_short_ratio === Infinity || performance_metrics.long_short_ratio === null ? '∞' : performance_metrics.long_short_ratio.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* Final Positions */}
        {final_portfolio.positions && (
          <div>
            <h4 className="font-medium mb-2">Final Positions</h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ticker</TableHead>
                  <TableHead>Long Shares</TableHead>
                  <TableHead>Short Shares</TableHead>
                  <TableHead>Long Cost Basis</TableHead>
                  <TableHead>Short Cost Basis</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(final_portfolio.positions).map(([ticker, position]: [string, any]) => (
                  <TableRow key={ticker}>
                    <TableCell className="font-medium">{ticker}</TableCell>
                    <TableCell className={cn(position.long > 0 ? "text-green-500" : "text-muted-foreground")}>
                      {position.long}
                    </TableCell>
                    <TableCell className={cn(position.short > 0 ? "text-red-500" : "text-muted-foreground")}>
                      {position.short}
                    </TableCell>
                    <TableCell>${position.long_cost_basis.toFixed(2)}</TableCell>
                    <TableCell>${position.short_cost_basis.toFixed(2)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Component for displaying real-time backtest performance
function BacktestPerformanceMetrics({ agentData }: { agentData: Record<string, any> }) {
  const backtestAgent = agentData['backtest'];
  
  if (!backtestAgent || !backtestAgent.backtestResults) return null;
  
  // Get the backtest results directly from the agent data
  const backtestResults = backtestAgent.backtestResults || [];
  
  if (backtestResults.length === 0) return null;
  
  const firstPeriod = backtestResults[0];
  const latestPeriod = backtestResults[backtestResults.length - 1];
  
  // Calculate performance metrics
  const initialValue = firstPeriod.portfolio_value;
  const currentValue = latestPeriod.portfolio_value;
  const totalReturn = ((currentValue - initialValue) / initialValue) * 100;
  
  // Calculate win rate (periods with positive returns)
  const periodReturns = backtestResults.slice(1).map((period: any, idx: number) => {
    const prevPeriod = backtestResults[idx];
    return ((period.portfolio_value - prevPeriod.portfolio_value) / prevPeriod.portfolio_value) * 100;
  });
  
  const winningPeriods = periodReturns.filter((ret: number) => ret > 0).length;
  const winRate = periodReturns.length > 0 ? (winningPeriods / periodReturns.length) * 100 : 0;
  
  // Calculate max drawdown
  let maxDrawdown = 0;
  let peak = initialValue;
  
  backtestResults.forEach((period: any) => {
    if (period.portfolio_value > peak) {
      peak = period.portfolio_value;
    }
    const drawdown = ((period.portfolio_value - peak) / peak) * 100;
    if (drawdown < maxDrawdown) {
      maxDrawdown = drawdown;
    }
  });
  
  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">Performance</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-xs text-muted-foreground">Total Return</div>
            <div className={cn("font-sm", totalReturn >= 0 ? "text-green-500" : "text-red-500")}>
              {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">Win Rate</div>
            <div className="font-sm">{winRate.toFixed(1)}%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">Max Drawdown</div>
            <div className="font-sm text-red-500">{Math.abs(maxDrawdown).toFixed(2)}%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">Periods Traded</div>
            <div className="font-sm">{backtestResults.length}</div>
          </div>
        </div>
        
        {/* Additional metrics */}
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-xs text-muted-foreground">Current Value</div>
            <div className="font-sm">${currentValue?.toLocaleString()}</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">Initial Value</div>
            <div className="font-sm">${initialValue?.toLocaleString()}</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">P&L</div>
            <div className={cn("font-sm", totalReturn >= 0 ? "text-green-500" : "text-red-500")}>
              ${(currentValue - initialValue).toLocaleString()}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">Long/Short Ratio</div>
            <div className="font-sm">
              {latestPeriod.long_short_ratio === Infinity || latestPeriod.long_short_ratio === null ? '∞' : latestPeriod.long_short_ratio?.toFixed(2)}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Main component for backtest output
export function BacktestOutput({ 
  agentData, 
  outputData 
}: { 
  agentData: Record<string, any>; 
  outputData: any; 
}) {
  return (
    <>
      <BacktestProgress agentData={agentData} />
      {outputData && <BacktestResults outputData={outputData} />}
      {agentData && agentData['backtest'] && (
        <BacktestPerformanceMetrics agentData={agentData} />
      )}
      <BacktestTradingTable agentData={agentData} />

    </>
  );
} 