import React, { useState, useEffect } from 'react';
import { MainNav } from '@/components/navigation/main-nav';
import { PortfolioDashboard } from '@/components/dashboard/portfolio-dashboard';
import { UniverseSelection } from '@/components/universe/universe-selection';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  BarChart3,
  Globe,
  MessageSquare,
  TrendingUp,
  AlertTriangle,
  Settings,
  Zap,
  LineChart,
  Activity,
  RefreshCw,
} from 'lucide-react';

// Feature Status Interface
interface FeatureStatus {
  basicFeatures: boolean;
  economicIndicators: boolean;
  politicalSignals: boolean;
  socialSentiment: boolean;
  financialData: boolean;
  apiKeysConfigured: {
    fred: boolean;
    newsapi: boolean;
    reddit: boolean;
    twitter: boolean;
    financialDatasets: boolean;
  };
}

// Placeholder components for features not yet implemented
const EconomicIndicators = () => (
  <div className="p-6">
    <h1 className="text-3xl font-bold mb-6">Economic Indicators</h1>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <BarChart3 className="h-5 w-5" />
            <span>Fed Funds Rate</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">5.25%</div>
          <p className="text-sm text-muted-foreground">+0.25% from last meeting</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5" />
            <span>Unemployment Rate</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">3.8%</div>
          <p className="text-sm text-muted-foreground">-0.1% from last month</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Activity className="h-5 w-5" />
            <span>Core CPI</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">2.1%</div>
          <p className="text-sm text-muted-foreground">Target: 2.0%</p>
        </CardContent>
      </Card>
    </div>
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Economic Health Score</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center space-x-4">
          <div className="text-3xl font-bold">72.5/100</div>
          <div className="flex-1">
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div className="bg-green-500 h-3 rounded-full" style={{ width: '72.5%' }}></div>
            </div>
          </div>
          <Badge variant="secondary" className="bg-green-100 text-green-800">
            Positive
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-2">
          Economic outlook appears positive with stable employment and controlled inflation.
        </p>
      </CardContent>
    </Card>
  </div>
);

const PoliticalSignals = () => (
  <div className="p-6">
    <h1 className="text-3xl font-bold mb-6">Political Signals</h1>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Globe className="h-5 w-5" />
            <span>Recent Events</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="border-l-4 border-yellow-500 pl-4">
              <h3 className="font-semibold">Infrastructure Bill Discussion</h3>
              <p className="text-sm text-muted-foreground">
                Congress debates $1.2T infrastructure package affecting industrials sector
              </p>
              <div className="flex items-center space-x-2 mt-2">
                <Badge variant="secondary">Medium Impact</Badge>
                <span className="text-xs text-muted-foreground">2 hours ago</span>
              </div>
            </div>
            <div className="border-l-4 border-green-500 pl-4">
              <h3 className="font-semibold">Trade Agreement Update</h3>
              <p className="text-sm text-muted-foreground">
                Positive developments in US-EU trade relations
              </p>
              <div className="flex items-center space-x-2 mt-2">
                <Badge variant="secondary">Low Impact</Badge>
                <span className="text-xs text-muted-foreground">1 day ago</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <AlertTriangle className="h-5 w-5" />
            <span>Risk Assessment</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">68/100</div>
          <p className="text-sm text-muted-foreground">Political Stability Score</p>
          <div className="mt-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span>Election Risk</span>
              <span className="text-green-600">Low</span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Policy Changes</span>
              <span className="text-yellow-600">Medium</span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Geopolitical</span>
              <span className="text-green-600">Low</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
);

const SentimentAnalysis = () => (
  <div className="p-6">
    <h1 className="text-3xl font-bold mb-6">Sentiment Analysis</h1>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {['AAPL', 'MSFT', 'GOOGL', 'TSLA'].map((ticker) => (
        <Card key={ticker}>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>{ticker}</span>
              <MessageSquare className="h-4 w-4" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">+0.45</div>
              <p className="text-sm text-muted-foreground">Sentiment Score</p>
              <div className="mt-2">
                <Badge variant="secondary">1,234 mentions</Badge>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                Trending: earnings beat
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Overall Market Sentiment</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-center">
          <div className="text-3xl font-bold text-green-600">+35%</div>
          <p className="text-sm text-muted-foreground">Bullish sentiment across major indices</p>
          <div className="mt-4 flex justify-center space-x-4">
            <Badge variant="secondary">Fear & Greed: 65</Badge>
            <Badge variant="secondary">VIX: 18.5</Badge>
            <Badge variant="secondary">Put/Call: 0.85</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
);

const MarketOverview = () => (
  <div className="p-6">
    <h1 className="text-3xl font-bold mb-6">Market Overview</h1>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Market Regime</p>
              <p className="text-2xl font-bold">Bull Market</p>
            </div>
            <TrendingUp className="h-8 w-8 text-green-600" />
          </div>
          <div className="mt-2">
            <Badge variant="secondary" className="bg-green-100 text-green-800">
              Strong Momentum
            </Badge>
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Economic Health</p>
              <p className="text-2xl font-bold">72.5/100</p>
            </div>
            <BarChart3 className="h-8 w-8 text-blue-600" />
          </div>
          <div className="mt-2">
            <Badge variant="secondary" className="bg-blue-100 text-blue-800">
              Positive
            </Badge>
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Sentiment</p>
              <p className="text-2xl font-bold">+35%</p>
            </div>
            <MessageSquare className="h-8 w-8 text-purple-600" />
          </div>
          <div className="mt-2">
            <Badge variant="secondary" className="bg-purple-100 text-purple-800">
              Bullish
            </Badge>
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Political Risk</p>
              <p className="text-2xl font-bold">Low</p>
            </div>
            <Globe className="h-8 w-8 text-yellow-600" />
          </div>
          <div className="mt-2">
            <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">
              Stable
            </Badge>
          </div>
        </CardContent>
      </Card>
    </div>
    
    <Card>
      <CardHeader>
        <CardTitle>Market Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground">
          Current market conditions favor growth strategies with strong economic fundamentals 
          supporting continued bull market momentum. Low political risk and positive sentiment 
          indicators suggest favorable conditions for equity investments.
        </p>
      </CardContent>
    </Card>
  </div>
);

const ComingSoon = ({ title }: { title: string }) => (
  <div className="p-6 text-center">
    <h1 className="text-3xl font-bold mb-4">{title}</h1>
    <Card className="max-w-md mx-auto">
      <CardContent className="p-8">
        <Zap className="h-16 w-16 mx-auto mb-4 text-gray-400" />
        <h2 className="text-xl font-semibold mb-2">Coming Soon</h2>
        <p className="text-muted-foreground">
          This feature is under development and will be available in the next release.
        </p>
      </CardContent>
    </Card>
  </div>
);

export function EnhancedLayout() {
  const [currentView, setCurrentView] = useState('portfolio-dashboard');
  const [featureStatus, setFeatureStatus] = useState<FeatureStatus | null>(null);

  useEffect(() => {
    // Fetch feature status on component mount
    fetchFeatureStatus();
  }, []);

  const fetchFeatureStatus = async () => {
    try {
      const response = await fetch('/api/v1/enhanced/status');
      if (response.ok) {
        const status = await response.json();
        setFeatureStatus(status);
      }
    } catch (error) {
      console.error('Error fetching feature status:', error);
      // Fallback to default status
      setFeatureStatus({
        basicFeatures: true,
        economicIndicators: false,
        politicalSignals: false,
        socialSentiment: false,
        financialData: false,
        apiKeysConfigured: {
          fred: false,
          newsapi: false,
          reddit: false,
          twitter: false,
          financialDatasets: false,
        },
      });
    }
  };

  const renderContent = () => {
    switch (currentView) {
      case 'portfolio':
      case 'portfolio-dashboard':
        return <PortfolioDashboard />;
      case 'universe':
      case 'universe-selection':
        return <UniverseSelection />;
      case 'economic-indicators':
        return <EconomicIndicators />;
      case 'political-signals':
        return <PoliticalSignals />;
      case 'sentiment-analysis':
        return <SentimentAnalysis />;
      case 'market-overview':
        return <MarketOverview />;
      case 'portfolio-holdings':
        return <ComingSoon title="Portfolio Holdings" />;
      case 'portfolio-performance':
        return <ComingSoon title="Portfolio Performance" />;
      case 'portfolio-risk':
        return <ComingSoon title="Portfolio Risk Analysis" />;
      case 'universe-screener':
        return <ComingSoon title="Security Screener" />;
      case 'universe-sectors':
        return <ComingSoon title="Sector Analysis" />;
      case 'agent-performance':
        return <ComingSoon title="AI Agent Performance" />;
      case 'agent-config':
        return <ComingSoon title="Agent Configuration" />;
      case 'decision-flow':
        return <ComingSoon title="Decision Flow Builder" />;
      case 'settings':
        return <ComingSoon title="Settings" />;
      default:
        return <PortfolioDashboard />;
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Top Navigation */}
      <header className="border-b bg-white">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <h1 className="text-xl font-bold">AI Hedge Fund</h1>
              <Badge variant="secondary">Enhanced</Badge>
            </div>
            <MainNav
              currentView={currentView}
              onViewChange={setCurrentView}
            />
          </div>
        </div>
      </header>

      {/* Feature Status Bar */}
      {featureStatus && (
        <div className="bg-blue-50 border-b px-6 py-2">
          <div className="flex items-center space-x-4 text-sm">
            <span className="font-medium">Features:</span>
            <div className="flex items-center space-x-1">
              <div className={`w-2 h-2 rounded-full ${featureStatus.basicFeatures ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span>Basic</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className={`w-2 h-2 rounded-full ${featureStatus.economicIndicators ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
              <span>Economic</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className={`w-2 h-2 rounded-full ${featureStatus.politicalSignals ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
              <span>Political</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className={`w-2 h-2 rounded-full ${featureStatus.socialSentiment ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
              <span>Sentiment</span>
            </div>
            {!featureStatus.economicIndicators && (
              <span className="text-xs text-muted-foreground ml-4">
                Add API keys in .env to enable all features
              </span>
            )}
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1">
        {renderContent()}
      </main>
    </div>
  );
}