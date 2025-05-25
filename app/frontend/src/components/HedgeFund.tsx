import React, { useState, useEffect } from 'react';
import { HedgeFundService } from '../services/hedgeFund';
import { AgentInfo, HedgeFundRequest, ProgressUpdate, HedgeFundResponse } from '../types/hedgeFund';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Checkbox } from './ui/checkbox';
import { Progress } from './ui/progress';
import { ScrollArea } from './ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { formatCurrency, formatPercent } from '../utils/format';

export function HedgeFund() {
    const [agents, setAgents] = useState<AgentInfo[]>([]);
    const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
    const [tickers, setTickers] = useState<string>('');
    const [initialCash, setInitialCash] = useState<number>(100000);
    const [marginRequirement, setMarginRequirement] = useState<number>(0);
    const [isRunning, setIsRunning] = useState<boolean>(false);
    const [progress, setProgress] = useState<ProgressUpdate[]>([]);
    const [result, setResult] = useState<HedgeFundResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadAgents();
    }, []);

    const loadAgents = async () => {
        try {
            const agents = await HedgeFundService.getAgents();
            setAgents(agents);
        } catch (error) {
            setError('Failed to load agents');
        }
    };

    const handleRun = async () => {
        setIsRunning(true);
        setProgress([]);
        setResult(null);
        setError(null);

        const request: HedgeFundRequest = {
            tickers: tickers.split(',').map(t => t.trim().toUpperCase()),
            selected_agents: selectedAgents,
            initial_cash: initialCash,
            margin_requirement: marginRequirement,
            model_name: 'gpt-4o',
            model_provider: 'openai',
            show_reasoning: true
        };

        try {
            await HedgeFundService.runHedgeFund(
                request,
                (update) => setProgress(prev => [...prev, update]),
                (data) => setResult(data),
                (error) => setError(error)
            );
        } catch (error) {
            setError('Failed to run hedge fund');
        } finally {
            setIsRunning(false);
        }
    };

    const toggleAgent = (agentName: string) => {
        setSelectedAgents(prev =>
            prev.includes(agentName)
                ? prev.filter(name => name !== agentName)
                : [...prev, agentName]
        );
    };

    return (
        <div className="container mx-auto p-4 space-y-4">
            <Card>
                <CardHeader>
                    <CardTitle>AI Hedge Fund</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-4">
                            <div>
                                <Label htmlFor="tickers">Stock Tickers (comma-separated)</Label>
                                <Input
                                    id="tickers"
                                    value={tickers}
                                    onChange={(e) => setTickers(e.target.value)}
                                    placeholder="AAPL, MSFT, GOOGL"
                                />
                            </div>
                            <div>
                                <Label htmlFor="initialCash">Initial Cash</Label>
                                <Input
                                    id="initialCash"
                                    type="number"
                                    value={initialCash}
                                    onChange={(e) => setInitialCash(Number(e.target.value))}
                                />
                            </div>
                            <div>
                                <Label htmlFor="marginRequirement">Margin Requirement</Label>
                                <Input
                                    id="marginRequirement"
                                    type="number"
                                    value={marginRequirement}
                                    onChange={(e) => setMarginRequirement(Number(e.target.value))}
                                />
                            </div>
                        </div>
                        <div>
                            <Label>Select Agents</Label>
                            <ScrollArea className="h-[200px] border rounded-md p-4">
                                <div className="space-y-2">
                                    {agents.map((agent) => (
                                        <div key={agent.name} className="flex items-center space-x-2">
                                            <Checkbox
                                                id={agent.name}
                                                checked={selectedAgents.includes(agent.name)}
                                                onCheckedChange={() => toggleAgent(agent.name)}
                                            />
                                            <Label htmlFor={agent.name} className="flex-1">
                                                {agent.name.replace(/_/g, ' ').toUpperCase()}
                                            </Label>
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </div>
                    </div>
                    <div className="mt-4">
                        <Button
                            onClick={handleRun}
                            disabled={isRunning || !tickers || selectedAgents.length === 0}
                        >
                            {isRunning ? 'Running...' : 'Run Hedge Fund'}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {error && (
                <Card className="bg-red-50">
                    <CardContent className="p-4">
                        <p className="text-red-600">{error}</p>
                    </CardContent>
                </Card>
            )}

            {isRunning && (
                <Card>
                    <CardHeader>
                        <CardTitle>Progress</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ScrollArea className="h-[400px]">
                            {progress.map((update, index) => (
                                <div key={index} className="mb-4 p-2 rounded-lg border border-border">
                                    <div className="flex items-center justify-between mb-1">
                                        <div className="flex items-center space-x-2">
                                            <span className="font-bold text-primary">{update.agent.replace('_agent', '').replace('_', ' ').toUpperCase()}</span>
                                            {update.ticker && (
                                                <span className="text-sm text-muted-foreground">[{update.ticker}]</span>
                                            )}
                                        </div>
                                        <span className="text-xs text-muted-foreground">
                                            {new Date(update.timestamp).toLocaleTimeString()}
                                        </span>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        {update.status.toLowerCase() === 'done' && (
                                            <span className="text-green-500">✓</span>
                                        )}
                                        {update.status.toLowerCase() === 'error' && (
                                            <span className="text-red-500">✗</span>
                                        )}
                                        {!update.status.toLowerCase().includes('done') && !update.status.toLowerCase().includes('error') && (
                                            <span className="text-yellow-500">⋯</span>
                                        )}
                                        <p className="text-sm">{update.status}</p>
                                    </div>
                                    {update.analysis && (
                                        <p className="text-sm text-muted-foreground mt-1 pl-6">{update.analysis}</p>
                                    )}
                                </div>
                            ))}
                        </ScrollArea>
                    </CardContent>
                </Card>
            )}

            {result && (
                <Tabs defaultValue="decisions">
                    <TabsList>
                        <TabsTrigger value="decisions">Trading Decisions</TabsTrigger>
                        <TabsTrigger value="portfolio">Portfolio</TabsTrigger>
                        <TabsTrigger value="signals">Analyst Signals</TabsTrigger>
                    </TabsList>
                    <TabsContent value="decisions">
                        <Card>
                            <CardContent className="p-4">
                                <ScrollArea className="h-[400px]">
                                    {Array.isArray(result.decisions) ? result.decisions.map((decision, index) => (
                                        <div key={index} className="mb-4 p-4 border rounded-md">
                                            <div className="flex justify-between items-center">
                                                <h3 className="font-bold">{decision.ticker}</h3>
                                                <span className={`px-2 py-1 rounded ${
                                                    decision.action === 'BUY' ? 'bg-green-100 text-green-800' :
                                                    decision.action === 'SELL' ? 'bg-red-100 text-red-800' :
                                                    'bg-gray-100 text-gray-800'
                                                }`}>
                                                    {decision.action}
                                                </span>
                                            </div>
                                            {decision.quantity && (
                                                <p>Quantity: {decision.quantity}</p>
                                            )}
                                            {decision.price && (
                                                <p>Price: {formatCurrency(decision.price)}</p>
                                            )}
                                            <p className="mt-2">{decision.reasoning}</p>
                                            <p className="text-sm text-gray-600 mt-1">
                                                Confidence: {formatPercent(decision.confidence)}
                                            </p>
                                        </div>
                                    )) : (
                                        <div className="text-center text-gray-500">No trading decisions available</div>
                                    )}
                                </ScrollArea>
                            </CardContent>
                        </Card>
                    </TabsContent>
                    <TabsContent value="portfolio">
                        <Card>
                            <CardContent className="p-4">
                                {result.portfolio_snapshot ? (
                                    <>
                                        <div className="mb-4">
                                            <h3 className="font-bold">Portfolio Summary</h3>
                                            <p>Cash: {formatCurrency(result.portfolio_snapshot.cash)}</p>
                                            <p>Total Value: {formatCurrency(result.portfolio_snapshot.total_value)}</p>
                                        </div>
                                        <ScrollArea className="h-[300px]">
                                            {Object.entries(result.portfolio_snapshot.positions).map(([ticker, position]) => (
                                                <div key={ticker} className="mb-4 p-4 border rounded-md">
                                                    <h4 className="font-bold">{ticker}</h4>
                                                    <p>Quantity: {position.quantity}</p>
                                                    <p>Average Price: {formatCurrency(position.average_price)}</p>
                                                    <p>Current Price: {formatCurrency(position.current_price)}</p>
                                                    <p>Market Value: {formatCurrency(position.market_value)}</p>
                                                    <p className={`${
                                                        position.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                                                    }`}>
                                                        Unrealized P&L: {formatCurrency(position.unrealized_pnl)} ({formatPercent(position.unrealized_pnl_percent)})
                                                    </p>
                                                </div>
                                            ))}
                                        </ScrollArea>
                                    </>
                                ) : (
                                    <div className="text-center text-gray-500">No portfolio data available</div>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>
                    <TabsContent value="signals">
                        <Card>
                            <CardContent className="p-4">
                                <ScrollArea className="h-[400px]">
                                    {result.analyst_signals ? (
                                        Object.entries(result.analyst_signals).map(([ticker, signals]) => (
                                            <div key={ticker} className="mb-4">
                                                <h3 className="font-bold mb-2">{ticker}</h3>
                                                {Array.isArray(signals) ? signals.map((signal, index) => (
                                                    <div key={index} className="mb-2 p-4 border rounded-md">
                                                        <div className="flex justify-between items-center">
                                                            <span className="font-bold">{signal.analyst}</span>
                                                            <span className={`px-2 py-1 rounded ${
                                                                signal.signal === 'BUY' ? 'bg-green-100 text-green-800' :
                                                                signal.signal === 'SELL' ? 'bg-red-100 text-red-800' :
                                                                'bg-gray-100 text-gray-800'
                                                            }`}>
                                                                {signal.signal}
                                                            </span>
                                                        </div>
                                                        <p className="mt-2">{signal.reasoning}</p>
                                                        <p className="text-sm text-gray-600 mt-1">
                                                            Confidence: {formatPercent(signal.confidence)}
                                                        </p>
                                                    </div>
                                                )) : (
                                                    <div className="text-center text-gray-500">No signals available for this ticker</div>
                                                )}
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-center text-gray-500">No analyst signals available</div>
                                    )}
                                </ScrollArea>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            )}
        </div>
    );
} 