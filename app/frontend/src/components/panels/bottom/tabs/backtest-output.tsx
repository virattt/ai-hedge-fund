import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useI18n } from '@/i18n/use-i18n';
import { cn } from '@/lib/utils';
import { MoreHorizontal } from 'lucide-react';
import { getActionColor } from './output-tab-utils';

// Component for displaying backtest progress
function BacktestProgress({ agentData }: { agentData: Record<string, any> }) {
  const backtestAgent = agentData['backtest'];
  const { t } = useI18n();

  if (!backtestAgent) return null;

  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">{t('bottom.backtestProgress')}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Current Status */}
          <div className="flex items-center gap-2">
            <MoreHorizontal className="h-4 w-4 text-yellow-500" />
            <span className="font-medium">{t('bottom.backtestRunner')}</span>
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
  const { t, translateAction } = useI18n();

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
        <CardTitle className="text-lg">{t('bottom.activity')}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="max-h-96 overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('table.date')}</TableHead>
                <TableHead>{t('table.ticker')}</TableHead>
                <TableHead>{t('table.action')}</TableHead>
                <TableHead>{t('table.quantity')}</TableHead>
                <TableHead>{t('table.price')}</TableHead>
                <TableHead>{t('table.shares')}</TableHead>
                <TableHead>{t('table.positionValue')}</TableHead>
                <TableHead>{t('table.bullish')}</TableHead>
                <TableHead>{t('table.bearish')}</TableHead>
                <TableHead>{t('table.neutral')}</TableHead>
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
                          {translateAction(row.action || 'hold')}
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
  const { t } = useI18n();

  if (!outputData) {
    return null;
  }

  console.log("outputData", outputData);

  if (!outputData.performance_metrics) {
    return (
      <Card className="bg-transparent mb-4">
        <CardHeader>
          <CardTitle className="text-lg">{t('bottom.backtestResults')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            {t('bottom.backtestCompleteNoMetrics')}
          </div>
        </CardContent>
      </Card>
    );
  }

  const { performance_metrics, final_portfolio, total_days } = outputData;

  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">{t('bottom.backtestResults')}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {/* Performance Metrics */}
          <div className="space-y-2">
            <h4 className="font-medium">{t('bottom.performanceMetrics')}</h4>
            <div className="space-y-1 text-sm">
              {performance_metrics.sharpe_ratio !== null && performance_metrics.sharpe_ratio !== undefined && (
                <div className="flex justify-between">
                  <span>{t('table.sharpeRatio')}:</span>
                  <span className={cn("font-medium", performance_metrics.sharpe_ratio > 1 ? "text-green-500" : "text-red-500")}>
                    {performance_metrics.sharpe_ratio.toFixed(2)}
                  </span>
                </div>
              )}
              {performance_metrics.sortino_ratio !== null && performance_metrics.sortino_ratio !== undefined && (
                <div className="flex justify-between">
                  <span>{t('table.sortinoRatio')}:</span>
                  <span className={cn("font-medium", performance_metrics.sortino_ratio > 1 ? "text-green-500" : "text-red-500")}>
                    {performance_metrics.sortino_ratio.toFixed(2)}
                  </span>
                </div>
              )}
              {performance_metrics.max_drawdown !== null && performance_metrics.max_drawdown !== undefined && (
                <div className="flex justify-between">
                  <span>{t('table.maxDrawdown')}:</span>
                  <span className="font-medium text-red-500">
                    {Math.abs(performance_metrics.max_drawdown).toFixed(2)}%
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Portfolio Summary */}
          <div className="space-y-2">
            <h4 className="font-medium">{t('bottom.portfolioSummary')}</h4>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span>{t('table.totalDays')}:</span>
                <span className="font-medium">{total_days}</span>
              </div>
              <div className="flex justify-between">
                <span>{t('table.finalCash')}:</span>
                <span className="font-medium">${final_portfolio.cash.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span>{t('table.marginUsed')}:</span>
                <span className="font-medium">${final_portfolio.margin_used.toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* Exposure Metrics */}
          <div className="space-y-2">
            <h4 className="font-medium">{t('bottom.exposureMetrics')}</h4>
            <div className="space-y-1 text-sm">
              {performance_metrics.gross_exposure !== null && performance_metrics.gross_exposure !== undefined && (
                <div className="flex justify-between">
                  <span>{t('table.grossExposure')}:</span>
                  <span className="font-medium">${performance_metrics.gross_exposure.toLocaleString()}</span>
                </div>
              )}
              {performance_metrics.net_exposure !== null && performance_metrics.net_exposure !== undefined && (
                <div className="flex justify-between">
                  <span>{t('table.netExposure')}:</span>
                  <span className="font-medium">${performance_metrics.net_exposure.toLocaleString()}</span>
                </div>
              )}
              {performance_metrics.long_short_ratio !== null && performance_metrics.long_short_ratio !== undefined && (
                <div className="flex justify-between">
                  <span>{t('table.longShortRatio')}:</span>
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
            <h4 className="font-medium mb-2">{t('bottom.finalPositions')}</h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('table.ticker')}</TableHead>
                  <TableHead>{t('table.longShares')}</TableHead>
                  <TableHead>{t('table.shortShares')}</TableHead>
                  <TableHead>{t('table.longCostBasis')}</TableHead>
                  <TableHead>{t('table.shortCostBasis')}</TableHead>
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
  const { t } = useI18n();

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
        <CardTitle className="text-lg">{t('bottom.performance')}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-xs text-muted-foreground">{t('table.totalReturn')}</div>
            <div className={cn("font-sm", totalReturn >= 0 ? "text-green-500" : "text-red-500")}>
              {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">{t('table.winRate')}</div>
            <div className="font-sm">{winRate.toFixed(1)}%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">{t('table.maxDrawdown')}</div>
            <div className="font-sm text-red-500">{Math.abs(maxDrawdown).toFixed(2)}%</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">{t('table.periodsTraded')}</div>
            <div className="font-sm">{backtestResults.length}</div>
          </div>
        </div>

        {/* Additional metrics */}
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-xs text-muted-foreground">{t('table.currentValue')}</div>
            <div className="font-sm">${currentValue?.toLocaleString()}</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">{t('table.initialValue')}</div>
            <div className="font-sm">${initialValue?.toLocaleString()}</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">{t('table.pnl')}</div>
            <div className={cn("font-sm", totalReturn >= 0 ? "text-green-500" : "text-red-500")}>
              ${(currentValue - initialValue).toLocaleString()}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-muted-foreground">{t('table.longShortRatio')}</div>
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
