import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
  Target,
  Settings,
  TrendingUp,
  Shield,
  Zap,
  BarChart3,
  RefreshCw,
  CheckCircle,
  Circle,
  Search,
  Filter,
  Globe,
  Building,
  Cpu,
  HeartHandshake,
  Fuel,
  Home,
} from 'lucide-react';

interface UniverseInfo {
  name: string;
  description: string;
  assetClasses: string[];
  maxPositions?: number;
  includedTickers: string[];
  sectorFocus?: string[];
}

interface UniverseConfig {
  selectedUniverse: string;
  customFilters: {
    minMarketCap?: number;
    maxPositions?: number;
    sectors?: string[];
    excludedTickers?: string[];
  };
}

const SECTOR_ICONS = {
  technology: Cpu,
  healthcare: HeartHandshake,
  financials: Building,
  energy: Fuel,
  'real_estate': Home,
  communication: Globe,
  industrials: Settings,
  consumer_discretionary: TrendingUp,
  consumer_staples: Shield,
  utilities: Zap,
  materials: BarChart3,
};

const UNIVERSE_CARDS = [
  {
    name: 'sp500',
    title: 'S&P 500 Universe',
    description: 'Large-cap stocks with high liquidity and institutional quality',
    icon: Target,
    color: 'bg-blue-500',
    features: ['500+ Securities', 'High Liquidity', 'Low Volatility', 'Institutional Grade'],
    recommendedFor: 'Conservative growth strategies',
  },
  {
    name: 'tech',
    title: 'High-Volume Tech',
    description: 'Technology sector focus with high volume and growth potential',
    icon: Cpu,
    color: 'bg-purple-500',
    features: ['30 Positions Max', 'High Growth', 'Tech Focus', 'Innovation Leaders'],
    recommendedFor: 'Aggressive growth strategies',
  },
  {
    name: 'sector_etf',
    title: 'Sector ETFs',
    description: 'Diversified sector rotation with broad market exposure',
    icon: BarChart3,
    color: 'bg-green-500',
    features: ['Sector Rotation', '15 ETFs Max', 'Diversified', 'Low Fees'],
    recommendedFor: 'Balanced diversification',
  },
  {
    name: 'options',
    title: 'Options Universe',
    description: 'Liquid options markets for complex strategies and hedging',
    icon: Zap,
    color: 'bg-yellow-500',
    features: ['Options Trading', 'High Liquidity', 'Greeks Analysis', 'Advanced Strategies'],
    recommendedFor: 'Sophisticated trading strategies',
  },
  {
    name: 'conservative',
    title: 'Conservative Large Cap',
    description: 'Blue-chip dividend stocks with stable fundamentals',
    icon: Shield,
    color: 'bg-indigo-500',
    features: ['Dividend Focus', 'Low Risk', 'Quality Stocks', 'Stable Returns'],
    recommendedFor: 'Income-focused strategies',
  },
  {
    name: 'aggressive_growth',
    title: 'Aggressive Growth',
    description: 'High-growth tech stocks combined with options strategies',
    icon: TrendingUp,
    color: 'bg-red-500',
    features: ['Maximum Returns', 'Tech + Options', 'High Risk', 'Active Management'],
    recommendedFor: 'Maximum growth potential',
  },
];

export function UniverseSelection() {
  const [universes, setUniverses] = useState<UniverseInfo[]>([]);
  const [selectedUniverse, setSelectedUniverse] = useState<string>('sp500');
  const [universeDetails, setUniverseDetails] = useState<UniverseInfo | null>(null);
  const [config, setConfig] = useState<UniverseConfig>({
    selectedUniverse: 'sp500',
    customFilters: {},
  });
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchUniverses = async () => {
    try {
      const response = await fetch('/api/v1/enhanced/universes');
      if (response.ok) {
        const data = await response.json();
        setUniverses(data);
      }
    } catch (error) {
      console.error('Error fetching universes:', error);
      // Fallback to mock data
      setUniverses([
        {
          name: 'sp500',
          description: 'S&P 500 companies with high liquidity',
          assetClasses: ['equity'],
          maxPositions: 50,
          includedTickers: ['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
          sectorFocus: [],
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchUniverseDetails = async (universeName: string) => {
    try {
      const response = await fetch(`/api/v1/enhanced/universes/${universeName}`);
      if (response.ok) {
        const data = await response.json();
        setUniverseDetails(data);
      }
    } catch (error) {
      console.error('Error fetching universe details:', error);
    }
  };

  useEffect(() => {
    fetchUniverses();
  }, []);

  useEffect(() => {
    if (selectedUniverse) {
      fetchUniverseDetails(selectedUniverse);
    }
  }, [selectedUniverse]);

  const handleUniverseSelect = (universeName: string) => {
    setSelectedUniverse(universeName);
    setConfig(prev => ({
      ...prev,
      selectedUniverse: universeName,
    }));
  };

  const applyUniverseConfig = async () => {
    try {
      // Here you would save the configuration to the backend
      console.log('Applying universe configuration:', config);
      
      // Show success message
      alert('Universe configuration applied successfully!');
    } catch (error) {
      console.error('Error applying universe configuration:', error);
      alert('Error applying configuration. Please try again.');
    }
  };

  const filteredUniverseCards = UNIVERSE_CARDS.filter(card =>
    card.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    card.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getUniverseCard = (universeName: string) => {
    return UNIVERSE_CARDS.find(card => card.name === universeName);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Trading Universe Selection</h1>
          <p className="text-muted-foreground">
            Choose your investment universe and configure trading parameters
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchUniverses}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={applyUniverseConfig} className="bg-blue-600 hover:bg-blue-700">
            <CheckCircle className="h-4 w-4 mr-2" />
            Apply Configuration
          </Button>
        </div>
      </div>

      <Tabs defaultValue="selection" className="space-y-4">
        <TabsList>
          <TabsTrigger value="selection">Universe Selection</TabsTrigger>
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="selection" className="space-y-4">
          {/* Search and Filter */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-4">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                    <Input
                      placeholder="Search universes..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                </div>
                <Button variant="outline" size="sm">
                  <Filter className="h-4 w-4 mr-2" />
                  Filters
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Universe Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredUniverseCards.map((universe) => {
              const IconComponent = universe.icon;
              const isSelected = selectedUniverse === universe.name;
              
              return (
                <Card
                  key={universe.name}
                  className={`cursor-pointer transition-all hover:shadow-lg ${
                    isSelected ? 'ring-2 ring-blue-500 bg-blue-50' : ''
                  }`}
                  onClick={() => handleUniverseSelect(universe.name)}
                >
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div className={`w-12 h-12 rounded-lg ${universe.color} flex items-center justify-center`}>
                        <IconComponent className="h-6 w-6 text-white" />
                      </div>
                      {isSelected ? (
                        <CheckCircle className="h-6 w-6 text-blue-500" />
                      ) : (
                        <Circle className="h-6 w-6 text-gray-300" />
                      )}
                    </div>
                    <div>
                      <CardTitle className="text-xl">{universe.title}</CardTitle>
                      <p className="text-sm text-muted-foreground mt-2">
                        {universe.description}
                      </p>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {/* Features */}
                      <div className="flex flex-wrap gap-2">
                        {universe.features.map((feature) => (
                          <Badge key={feature} variant="secondary" className="text-xs">
                            {feature}
                          </Badge>
                        ))}
                      </div>
                      
                      <Separator />
                      
                      {/* Recommended For */}
                      <div>
                        <p className="text-sm font-medium text-gray-700">Recommended for:</p>
                        <p className="text-sm text-muted-foreground">{universe.recommendedFor}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="configuration" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Selected Universe Details */}
            {universeDetails && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Target className="h-5 w-5" />
                    <span>Selected Universe: {universeDetails.name}</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label className="text-sm font-medium">Description</Label>
                    <p className="text-sm text-muted-foreground">{universeDetails.description}</p>
                  </div>
                  
                  <div>
                    <Label className="text-sm font-medium">Asset Classes</Label>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {universeDetails.assetClasses.map((assetClass) => (
                        <Badge key={assetClass} variant="outline">
                          {assetClass}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {universeDetails.maxPositions && (
                    <div>
                      <Label className="text-sm font-medium">Maximum Positions</Label>
                      <p className="text-sm text-muted-foreground">{universeDetails.maxPositions}</p>
                    </div>
                  )}

                  <div>
                    <Label className="text-sm font-medium">
                      Included Tickers ({universeDetails.includedTickers.length})
                    </Label>
                    <div className="flex flex-wrap gap-1 mt-2 max-h-32 overflow-y-auto">
                      {universeDetails.includedTickers.slice(0, 20).map((ticker) => (
                        <Badge key={ticker} variant="secondary" className="text-xs">
                          {ticker}
                        </Badge>
                      ))}
                      {universeDetails.includedTickers.length > 20 && (
                        <Badge variant="secondary" className="text-xs">
                          +{universeDetails.includedTickers.length - 20} more
                        </Badge>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Custom Configuration */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Settings className="h-5 w-5" />
                  <span>Custom Configuration</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="minMarketCap">Minimum Market Cap (Billions)</Label>
                  <Input
                    id="minMarketCap"
                    type="number"
                    placeholder="e.g., 10"
                    value={config.customFilters.minMarketCap || ''}
                    onChange={(e) =>
                      setConfig(prev => ({
                        ...prev,
                        customFilters: {
                          ...prev.customFilters,
                          minMarketCap: Number(e.target.value) || undefined,
                        },
                      }))
                    }
                  />
                </div>

                <div>
                  <Label htmlFor="maxPositions">Maximum Positions</Label>
                  <Input
                    id="maxPositions"
                    type="number"
                    placeholder="e.g., 25"
                    value={config.customFilters.maxPositions || ''}
                    onChange={(e) =>
                      setConfig(prev => ({
                        ...prev,
                        customFilters: {
                          ...prev.customFilters,
                          maxPositions: Number(e.target.value) || undefined,
                        },
                      }))
                    }
                  />
                </div>

                <div>
                  <Label>Sector Focus</Label>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {Object.entries(SECTOR_ICONS).map(([sector, IconComponent]) => (
                      <div key={sector} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          id={sector}
                          checked={config.customFilters.sectors?.includes(sector) || false}
                          onChange={(e) => {
                            const sectors = config.customFilters.sectors || [];
                            if (e.target.checked) {
                              setConfig(prev => ({
                                ...prev,
                                customFilters: {
                                  ...prev.customFilters,
                                  sectors: [...sectors, sector],
                                },
                              }));
                            } else {
                              setConfig(prev => ({
                                ...prev,
                                customFilters: {
                                  ...prev.customFilters,
                                  sectors: sectors.filter(s => s !== sector),
                                },
                              }));
                            }
                          }}
                        />
                        <Label htmlFor={sector} className="flex items-center space-x-2 cursor-pointer">
                          <IconComponent className="h-4 w-4" />
                          <span className="text-sm capitalize">{sector.replace('_', ' ')}</span>
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <Label htmlFor="excludedTickers">Excluded Tickers (comma-separated)</Label>
                  <Input
                    id="excludedTickers"
                    placeholder="e.g., TSLA, GME, AMC"
                    value={config.customFilters.excludedTickers?.join(', ') || ''}
                    onChange={(e) =>
                      setConfig(prev => ({
                        ...prev,
                        customFilters: {
                          ...prev.customFilters,
                          excludedTickers: e.target.value
                            .split(',')
                            .map(ticker => ticker.trim().toUpperCase())
                            .filter(ticker => ticker.length > 0),
                        },
                      }))
                    }
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="analysis" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Universe Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="text-center p-4 border rounded-lg">
                  <p className="text-2xl font-bold text-blue-600">
                    {universeDetails?.includedTickers.length || 0}
                  </p>
                  <p className="text-sm text-muted-foreground">Total Securities</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <p className="text-2xl font-bold text-green-600">
                    {universeDetails?.maxPositions || 'Unlimited'}
                  </p>
                  <p className="text-sm text-muted-foreground">Max Positions</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <p className="text-2xl font-bold text-purple-600">
                    {universeDetails?.assetClasses.length || 0}
                  </p>
                  <p className="text-sm text-muted-foreground">Asset Classes</p>
                </div>
              </div>
              
              <Separator className="my-6" />
              
              <div>
                <h3 className="text-lg font-semibold mb-4">Configuration Summary</h3>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <pre className="text-sm">
                    {JSON.stringify(config, null, 2)}
                  </pre>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}