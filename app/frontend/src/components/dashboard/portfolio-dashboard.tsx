import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Target,
  AlertTriangle,
  RefreshCw,
  BarChart3,
  PieChart,
  Activity,
  Calendar,
} from 'lucide-react';
import { LineChart, Line, AreaChart, Area, PieChart as RechartsPieChart, Cell, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

interface PortfolioMetrics {
  totalValue: number;
  cashBalance: number;
  totalReturn: number;
  totalReturnPercent: number;
  dayChange: number;
  dayChangePercent: number;
  allocatedValue: number;
  availableCash: number;
}

interface Position {
  ticker: string;
  shares: number;
  averagePrice: number;
  currentPrice: number;
  marketValue: number;
  unrealizedPnL: number;
  unrealizedPnLPercent: number;
  weight: number;
  sector: string;
}

interface MarketOverview {
  marketRegime: string;
  economicHealth: number;
  averageSentiment: number;
  highImpactPoliticalEvents: number;
  economicSummary: string;
  lastUpdated: string;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

export function PortfolioDashboard() {
  const [portfolioMetrics, setPortfolioMetrics] = useState<PortfolioMetrics | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const fetchPortfolioData = async () => {
    setIsLoading(true);
    try {
      // Simulate API calls (replace with actual API endpoints)
      const mockMetrics: PortfolioMetrics = {
        totalValue: 125650.75,
        cashBalance: 25650.75,
        totalReturn: 25650.75,
        totalReturnPercent: 25.65,
        dayChange: 1250.30,
        dayChangePercent: 1.01,
        allocatedValue: 100000,
        availableCash: 25650.75,
      };

      const mockPositions: Position[] = [
        {
          ticker: 'AAPL',
          shares: 100,
          averagePrice: 150.00,
          currentPrice: 175.50,
          marketValue: 17550,
          unrealizedPnL: 2550,
          unrealizedPnLPercent: 17.0,
          weight: 0.35,
          sector: 'Technology',
        },
        {
          ticker: 'MSFT',
          shares: 75,
          averagePrice: 250.00,
          currentPrice: 280.25,
          marketValue: 21018.75,
          unrealizedPnL: 2268.75,
          unrealizedPnLPercent: 12.1,
          weight: 0.42,
          sector: 'Technology',
        },
        {
          ticker: 'GOOGL',
          shares: 25,
          averagePrice: 120.00,
          currentPrice: 138.75,
          marketValue: 3468.75,
          unrealizedPnL: 468.75,
          unrealizedPnLPercent: 15.6,
          weight: 0.07,
          sector: 'Technology',
        },
      ];

      // Fetch market overview
      const response = await fetch('/api/v1/enhanced/market-overview');
      const marketData = response.ok ? await response.json() : {
        marketRegime: 'Bull Market',
        economicHealth: 72.5,
        averageSentiment: 0.35,
        highImpactPoliticalEvents: 1,
        economicSummary: 'Economic outlook appears positive',
        lastUpdated: new Date().toISOString(),
      };

      setPortfolioMetrics(mockMetrics);
      setPositions(mockPositions);
      setMarketOverview(marketData);
      setLastRefresh(new Date());
    } catch (error) {
      console.error('Error fetching portfolio data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolioData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchPortfolioData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const sectorAllocation = positions.reduce((acc, position) => {
    const sector = position.sector;
    if (!acc[sector]) {
      acc[sector] = { value: 0, count: 0 };
    }
    acc[sector].value += position.marketValue;
    acc[sector].count += 1;
    return acc;
  }, {} as Record<string, { value: number; count: number }>);

  const sectorData = Object.entries(sectorAllocation).map(([sector, data]) => ({
    name: sector,
    value: data.value,
    count: data.count,
  }));

  const performanceData = [
    { date: '2024-01', value: 100000 },
    { date: '2024-02', value: 105000 },
    { date: '2024-03', value: 108000 },
    { date: '2024-04', value: 112000 },
    { date: '2024-05', value: 118000 },
    { date: '2024-06', value: 125650 },
  ];

  const getMarketRegimeColor = (regime: string) => {
    switch (regime.toLowerCase()) {
      case 'bull market': return 'bg-green-500';
      case 'bear market': return 'bg-red-500';
      case 'sideways market': return 'bg-yellow-500';
      case 'volatile market': return 'bg-orange-500';
      default: return 'bg-gray-500';
    }
  };

  const getMarketRegimeIcon = (regime: string) => {
    switch (regime.toLowerCase()) {
      case 'bull market': return <TrendingUp className="h-4 w-4" />;
      case 'bear market': return <TrendingDown className="h-4 w-4" />;
      default: return <Activity className="h-4 w-4" />;
    }
  };

  if (isLoading && !portfolioMetrics) {
    return (
      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-6">
                <div className="h-20 bg-gray-200 rounded"></div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Portfolio Dashboard</h1>
          <p className="text-muted-foreground">
            Last updated: {lastRefresh.toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchPortfolioData}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Market Overview */}
      {marketOverview && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Activity className="h-5 w-5" />
              <span>Market Overview</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="flex items-center space-x-3">
                <div className={`w-3 h-3 rounded-full ${getMarketRegimeColor(marketOverview.marketRegime)}`}></div>
                <div>
                  <p className="text-sm text-muted-foreground">Market Regime</p>
                  <p className="font-semibold flex items-center space-x-1">
                    {getMarketRegimeIcon(marketOverview.marketRegime)}
                    <span>{marketOverview.marketRegime}</span>
                  </p>
                </div>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Economic Health</p>
                <p className="font-semibold">{marketOverview.economicHealth.toFixed(1)}/100</p>
                <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${marketOverview.economicHealth}%` }}
                  ></div>
                </div>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Market Sentiment</p>
                <div className="flex items-center space-x-2">
                  <p className="font-semibold">
                    {marketOverview.averageSentiment > 0 ? '+' : ''}{(marketOverview.averageSentiment * 100).toFixed(1)}%
                  </p>
                  {marketOverview.averageSentiment > 0 ? (
                    <TrendingUp className="h-4 w-4 text-green-500" />
                  ) : (
                    <TrendingDown className="h-4 w-4 text-red-500" />
                  )}
                </div>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Political Events</p>
                <div className="flex items-center space-x-2">
                  <p className="font-semibold">{marketOverview.highImpactPoliticalEvents}</p>
                  <AlertTriangle className="h-4 w-4 text-yellow-500" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Key Metrics */}
      {portfolioMetrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Total Value</p>
                  <p className="text-2xl font-bold">${portfolioMetrics.totalValue.toLocaleString()}</p>
                </div>
                <DollarSign className="h-8 w-8 text-green-600" />
              </div>
              <div className="mt-2 flex items-center text-sm">
                <TrendingUp className="h-4 w-4 text-green-500 mr-1" />
                <span className="text-green-600">
                  +{portfolioMetrics.dayChangePercent.toFixed(2)}% today
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Total Return</p>
                  <p className="text-2xl font-bold">
                    ${portfolioMetrics.totalReturn.toLocaleString()}
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-green-600" />
              </div>
              <div className="mt-2">
                <Badge variant="secondary" className="text-green-600">
                  +{portfolioMetrics.totalReturnPercent.toFixed(2)}%
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Cash Balance</p>
                  <p className="text-2xl font-bold">${portfolioMetrics.cashBalance.toLocaleString()}</p>
                </div>
                <Target className="h-8 w-8 text-blue-600" />
              </div>
              <div className="mt-2">
                <p className="text-sm text-muted-foreground">
                  {((portfolioMetrics.cashBalance / portfolioMetrics.totalValue) * 100).toFixed(1)}% of portfolio
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Day Change</p>
                  <p className="text-2xl font-bold">
                    ${portfolioMetrics.dayChange.toLocaleString()}
                  </p>
                </div>
                <Activity className="h-8 w-8 text-orange-600" />
              </div>
              <div className="mt-2">
                <Badge variant="secondary" className="text-green-600">
                  +{portfolioMetrics.dayChangePercent.toFixed(2)}%
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Charts and Tables */}
      <Tabs defaultValue="performance" className="space-y-4">
        <TabsList>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="positions">Positions</TabsTrigger>
          <TabsTrigger value="allocation">Allocation</TabsTrigger>
        </TabsList>

        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <BarChart3 className="h-5 w-5" />
                <span>Portfolio Performance</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={performanceData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#8884d8"
                    fill="#8884d8"
                    fillOpacity={0.3}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="positions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Current Positions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {positions.map((position) => (
                  <div
                    key={position.ticker}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div className="flex items-center space-x-4">
                      <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                        <span className="font-semibold text-blue-600">
                          {position.ticker.substring(0, 2)}
                        </span>
                      </div>
                      <div>
                        <p className="font-semibold">{position.ticker}</p>
                        <p className="text-sm text-muted-foreground">{position.sector}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold">${position.marketValue.toLocaleString()}</p>
                      <p className="text-sm text-muted-foreground">
                        {position.shares} shares @ ${position.currentPrice.toFixed(2)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`font-semibold ${position.unrealizedPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {position.unrealizedPnL >= 0 ? '+' : ''}${position.unrealizedPnL.toLocaleString()}
                      </p>
                      <p className={`text-sm ${position.unrealizedPnLPercent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {position.unrealizedPnLPercent >= 0 ? '+' : ''}{position.unrealizedPnLPercent.toFixed(2)}%
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold">{(position.weight * 100).toFixed(1)}%</p>
                      <p className="text-sm text-muted-foreground">weight</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="allocation" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <PieChart className="h-5 w-5" />
                  <span>Sector Allocation</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <RechartsPieChart>
                    <Pie
                      data={sectorData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={120}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {sectorData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Allocation Details</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {sectorData.map((sector, index) => (
                    <div key={sector.name} className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div
                          className="w-4 h-4 rounded"
                          style={{ backgroundColor: COLORS[index % COLORS.length] }}
                        ></div>
                        <span className="font-medium">{sector.name}</span>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold">${sector.value.toLocaleString()}</p>
                        <p className="text-sm text-muted-foreground">
                          {((sector.value / portfolioMetrics!.totalValue) * 100).toFixed(1)}%
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}