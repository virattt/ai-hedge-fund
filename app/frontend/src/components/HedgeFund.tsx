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
                                            <div className="flex items-center space-x-2 flex-1">
                                                <img
                                                    src={`/images/analysts/${agent.name.toLowerCase().replace(/\s+/g, '_')}.png`}
                                                    alt={agent.name}
                                                    className="w-8 h-8 rounded-full object-cover"
                                                    onError={(e) => {
                                                        if (e.currentTarget.src.endsWith('.png')) {
                                                            e.currentTarget.src = e.currentTarget.src.replace('.png', '.jpg');
                                                        } else {
                                                            e.currentTarget.src = '/images/analysts/default.png';
                                                        }
                                                    }}
                                                />
                                                <Label htmlFor={agent.name} className="flex-1">
                                                    {agent.name.replace(/_/g, ' ').toUpperCase()}
                                                </Label>
                                            </div>
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
                            <CardHeader>
                                <CardTitle>Trading Decisions</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {result.decisions && result.decisions.length > 0 ? (
                                    <ScrollArea className="h-[400px]">
                                        {result.decisions.map((decision, index) => (
                                            <div key={index} className="mb-4 p-4 rounded-lg border border-border">
                                                <div className="flex items-center justify-between mb-2">
                                                    <div className="flex items-center space-x-2">
                                                        <span className="font-bold text-primary">{decision.ticker}</span>
                                                        <span className={`px-2 py-1 rounded text-sm ${
                                                            decision.action === 'BUY' ? 'bg-green-100 text-green-800' :
                                                            decision.action === 'SELL' ? 'bg-red-100 text-red-800' :
                                                            'bg-gray-100 text-gray-800'
                                                        }`}>
                                                            {decision.action}
                                                        </span>
                                                    </div>
                                                    <span className="text-xs text-muted-foreground">
                                                        {new Date(decision.timestamp).toLocaleString()}
                                                    </span>
                                                </div>
                                                <div className="space-y-2">
                                                    {decision.quantity && (
                                                        <p className="text-sm">
                                                            <span className="font-medium">Quantity:</span> {decision.quantity}
                                                        </p>
                                                    )}
                                                    {decision.price && (
                                                        <p className="text-sm">
                                                            <span className="font-medium">Price:</span> {formatCurrency(decision.price)}
                                                        </p>
                                                    )}
                                                    <p className="text-sm">
                                                        <span className="font-medium">Confidence:</span> {formatPercent(decision.confidence)}
                                                    </p>
                                                    <p className="text-sm text-muted-foreground">{decision.reasoning}</p>
                                                </div>
                                            </div>
                                        ))}
                                    </ScrollArea>
                                ) : (
                                    <div className="text-center py-8 text-muted-foreground">
                                        No trading decisions available
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>
                    <TabsContent value="portfolio">
                        <Card>
                            <CardHeader>
                                <CardTitle>Portfolio Summary</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <p className="text-sm font-medium">Cash</p>
                                            <p className="text-2xl font-bold">{formatCurrency(result.portfolio_snapshot.cash)}</p>
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium">Total Value</p>
                                            <p className="text-2xl font-bold">{formatCurrency(result.portfolio_snapshot.total_value)}</p>
                                        </div>
                                    </div>
                                    <div className="space-y-4">
                                        {Object.entries(result.portfolio_snapshot.positions).map(([ticker, position]) => (
                                            <div key={ticker} className="p-4 rounded-lg border border-border">
                                                <div className="flex items-center justify-between mb-2">
                                                    <span className="font-bold text-primary">{ticker}</span>
                                                </div>
                                                <div className="grid grid-cols-2 gap-4">
                                                    <div>
                                                        <p className="text-sm font-medium">Quantity</p>
                                                        <p className="text-lg">{position.quantity}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-medium">Average Price</p>
                                                        <p className="text-lg">{formatCurrency(position.average_price)}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-medium">Current Price</p>
                                                        <p className="text-lg">{formatCurrency(position.current_price)}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-medium">Market Value</p>
                                                        <p className="text-lg">{formatCurrency(position.market_value)}</p>
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-medium">Unrealized P&L</p>
                                                        <p className="text-lg">{formatCurrency(position.unrealized_pnl)} ({formatPercent(position.unrealized_pnl_percent)})</p>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                    <TabsContent value="signals">
                        <Card>
                            <CardHeader>
                                <CardTitle>Analyst Signals</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {result && result.analyst_signals ? (
                                    Object.keys(result.analyst_signals).length > 0 ? (
                                        Object.entries(result.analyst_signals).map(([ticker, signals]) => (
                                            <div key={ticker} className="mb-6">
                                                <h3 className="text-lg font-bold mb-2">{ticker}</h3>
                                                {Array.isArray(signals) && signals.length > 0 ? (
                                                    <div className="space-y-4">
                                                        {signals.map((signal, index) => (
                                                            <div key={index} className="p-4 rounded-lg border border-border">
                                                                <div className="flex items-center justify-between mb-2">
                                                                    <div className="flex items-center space-x-2">
                                                                        <div className="flex items-center space-x-2">
                                                                            <img
                                                                                src={`/images/analysts/${signal.analyst.toLowerCase().replace(/\s+/g, '_')}.png`}
                                                                                alt={signal.analyst}
                                                                                className="w-10 h-10 rounded-full object-cover"
                                                                                onError={(e) => {
                                                                                    if (e.currentTarget.src.endsWith('.png')) {
                                                                                        e.currentTarget.src = e.currentTarget.src.replace('.png', '.jpg');
                                                                                    } else {
                                                                                        e.currentTarget.src = '/images/analysts/default.png';
                                                                                    }
                                                                                }}
                                                                            />
                                                                            <span className="font-medium">{signal.analyst || 'Unknown Analyst'}</span>
                                                                        </div>
                                                                        <span className={`px-2 py-1 rounded text-sm ${
                                                                            signal.signal === 'BUY' ? 'bg-green-100 text-green-800' :
                                                                            signal.signal === 'SELL' ? 'bg-red-100 text-red-800' :
                                                                            'bg-gray-100 text-gray-800'
                                                                        }`}>
                                                                            {signal.signal || 'HOLD'}
                                                                        </span>
                                                                    </div>
                                                                    <span className="text-xs text-muted-foreground">
                                                                        {signal.timestamp ? new Date(signal.timestamp).toLocaleString() : 'No timestamp'}
                                                                    </span>
                                                                </div>
                                                                <div className="space-y-2">
                                                                    <p className="text-sm">
                                                                        <span className="font-medium">Confidence:</span> {formatPercent(signal.confidence || 0)}
                                                                    </p>
                                                                    <p className="text-sm text-muted-foreground">{signal.reasoning || 'No reasoning provided'}</p>
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <div className="text-center py-4 text-muted-foreground">
                                                        No analyst signals available for {ticker}
                                                    </div>
                                                )}
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-center py-8 text-muted-foreground">
                                            No analyst signals available
                                        </div>
                                    )
                                ) : (
                                    <div className="text-center py-8 text-muted-foreground">
                                        No analyst signals available
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            )}
        </div>
    );
} 