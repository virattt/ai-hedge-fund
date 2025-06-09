import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Play, BarChart3, Loader2, TrendingUp, TrendingDown, Minus, Target, AlertTriangle } from 'lucide-react';
import { SWARM_NAMES } from '../data/multi-node-mappings';
import { apiModels, defaultModel, ModelItem } from '../data/models';

interface Position {
  ticker: string;
  long_shares: number;
  short_shares: number;
  long_cost_basis: number;
  short_cost_basis: number;
}

interface PortfolioPosition {
  long: number;
  short: number;
  long_cost_basis: number;
  short_cost_basis: number;
  short_margin_used: number;
}

interface Portfolio {
  cash: number;
  margin_requirement: number;
  margin_used: number;
  positions: Record<string, PortfolioPosition>;
  realized_gains: Record<string, {
    long: number;
    short: number;
  }>;
}

interface AnalysisResult {
  ticker: string;
  swarm: string;
  status: 'running' | 'completed' | 'error';
  result?: unknown;
  timestamp: Date;
  detailedAnalysis?: {
    decisions?: Record<string, TradingDecision>;
    analyst_signals?: Record<string, Record<string, AnalystSignal>>;
  };
}

interface TradingDecision {
  action: 'buy' | 'sell' | 'hold';
  quantity: number;
  confidence: number;
  reasoning: string;
}

interface AnalystSignal {
  signal?: 'bullish' | 'bearish' | 'neutral';
  confidence?: number;
  reasoning?: string | Record<string, number>;
  remaining_position_limit?: number;
  current_price?: number;
  strategy_signals?: Record<string, StrategySignal>;
}

interface StrategySignal {
  signal: 'bullish' | 'bearish' | 'neutral';
  confidence: number;
  metrics?: Record<string, number>;
}

export function Portfolio() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [initialCash, setInitialCash] = useState('100000');
  const [marginRequirement, setMarginRequirement] = useState('0.5');
  const [tickers, setTickers] = useState('AAPL,MSFT,GOOGL,TSLA');
  const [selectedSwarm, setSelectedSwarm] = useState<string>('Technical Analysis Team');
  const [selectedModel, setSelectedModel] = useState<ModelItem>(defaultModel || apiModels[0]);
  const [analysisDateRange, setAnalysisDateRange] = useState<string>('30'); // days
  const [customStartDate, setCustomStartDate] = useState<string>('');
  const [customEndDate, setCustomEndDate] = useState<string>('');
  const [analysisResults, setAnalysisResults] = useState<AnalysisResult[]>([]);
  const [runningAnalyses, setRunningAnalyses] = useState<Set<string>>(new Set());
  const [viewingResult, setViewingResult] = useState<AnalysisResult | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<Record<string, {
    currentAgent: string;
    completedAgents: string[];
    totalAgents: number;
    progress: number;
    agentProgresses: Record<string, number>;
  }>>({});
  const [newPosition, setNewPosition] = useState<Position>({
    ticker: '',
    long_shares: 0,
    short_shares: 0,
    long_cost_basis: 0,
    short_cost_basis: 0,
  });

  // Load existing portfolio on component mount
  useEffect(() => {
    fetchPortfolio();
  }, []);

  const fetchPortfolio = async () => {
    try {
      const response = await fetch('http://localhost:8000/portfolio/');
      if (response.ok) {
        const data = await response.json();
        setPortfolio(data);
      }
    } catch (error) {
      console.error('Error fetching portfolio:', error);
    }
  };

  const createPortfolio = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/portfolio/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          initial_cash: parseFloat(initialCash),
          margin_requirement: parseFloat(marginRequirement),
          tickers: tickers.split(',').map(t => t.trim()),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setPortfolio(data.portfolio);
      } else {
        console.error('Error creating portfolio');
      }
    } catch (error) {
      console.error('Error creating portfolio:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const updatePosition = async () => {
    if (!newPosition.ticker || !portfolio) return;

    try {
      const response = await fetch('http://localhost:8000/portfolio/positions', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          positions: [newPosition],
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setPortfolio(data.portfolio);
        // Reset form
        setNewPosition({
          ticker: '',
          long_shares: 0,
          short_shares: 0,
          long_cost_basis: 0,
          short_cost_basis: 0,
        });
      } else {
        const errorData = await response.json();
        console.error('Error updating position:', errorData);
        alert(`Failed to update position: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error updating position:', error);
      alert('Failed to update position. Please check your connection and try again.');
    }
  };

  const runAnalysisForTicker = async (ticker: string) => {
    // Prevent multiple analyses from running simultaneously
    if (runningAnalyses.size > 0) {
      alert('Please wait for the current analysis to complete before starting a new one.');
      return;
    }

    const analysisKey = `${ticker}-${selectedSwarm}`;
    setRunningAnalyses(prev => new Set([...prev, analysisKey]));

    // Initialize progress tracking
    const selectedAgents = getAgentsForSwarm(selectedSwarm);
    const expectedProgressAgents = getExpectedProgressAgents(selectedSwarm);
    setAnalysisProgress(prev => ({
      ...prev,
      [analysisKey]: {
        currentAgent: 'Initializing...',
        completedAgents: [],
        totalAgents: selectedAgents.length,
        progress: 0,
        agentProgresses: {} as Record<string, number>
      }
    }));

    try {
      // Simulate API call to hedge fund endpoint
      const { start_date, end_date } = getDateRange();
      
      const response = await fetch('http://localhost:8000/hedge-fund/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tickers: [ticker],
          selected_agents: getAgentsForSwarm(selectedSwarm),
          model_name: selectedModel.model_name,
          model_provider: selectedModel.provider,
          start_date,
          end_date,
          initial_cash: portfolio?.cash || 100000,
          margin_requirement: portfolio?.margin_requirement || 0.5,
          portfolio: portfolio, // Pass existing portfolio data
        }),
      });

      if (response.ok) {
        // Handle SSE response
        const reader = response.body?.getReader();
        if (reader) {
          // Process streaming response
          const decoder = new TextDecoder();
          let buffer = '';
          
          // eslint-disable-next-line no-constant-condition
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (data === '[DONE]') break;
                
                try {
                  const parsed = JSON.parse(data);
                  
                  // Handle progress updates
                  if (parsed.type === 'progress') {
                    setAnalysisProgress(prev => {
                      const current = prev[analysisKey] || { 
                        currentAgent: '', 
                        completedAgents: [], 
                        totalAgents: selectedAgents.length, 
                        progress: 0, 
                        agentProgresses: {} as Record<string, number>
                      };
                      
                      // Extract detailed status and agent info
                      const agentName = parsed.agent || 'Processing...';
                      const detailedStatus = parsed.status || parsed.data?.status || 'Working...';
                      const displayStatus = `${agentName}: ${detailedStatus}`;
                      
                      // Calculate individual agent progress
                      const agentProgress = getAgentProgressEstimate(agentName, detailedStatus);
                      const newAgentProgresses = { ...current.agentProgresses, [agentName]: agentProgress };
                      
                      // Update completed agents list
                      const newCompletedAgents = [...current.completedAgents];
                      if (parsed.status === 'Done' && expectedProgressAgents.includes(agentName)) {
                        // Only count agents that correspond to user-selected agents
                        const mappedAgent = mapBackendAgentToSelected(agentName);
                        if (mappedAgent && selectedAgents.includes(mappedAgent) && !newCompletedAgents.includes(mappedAgent)) {
                          newCompletedAgents.push(mappedAgent);
                        }
                      }
                      
                      // Calculate overall progress based on individual agent progress
                      let totalProgress = 0;
                      let activeAgents = 0;
                      
                      // Track progress for all expected agents (including portfolio_manager, risk_management_agent)
                      expectedProgressAgents.forEach(agent => {
                        const progressValue = (newAgentProgresses as Record<string, number>)[agent];
                        if (progressValue !== undefined) {
                          totalProgress += progressValue;
                          activeAgents++;
                        }
                      });
                      
                      // But calculate percentage based on selected agents count for user display
                      const divisor = activeAgents > 0 ? Math.max(activeAgents, selectedAgents.length) : selectedAgents.length;
                      const overallProgress = Math.round(totalProgress / divisor);
                      
                      console.log(`Selected agents: [${selectedAgents.join(', ')}] (${selectedAgents.length})`);
                      console.log(`Expected progress agents: [${expectedProgressAgents.join(', ')}]`);
                      console.log(`Active agent progresses:`, newAgentProgresses);
                      console.log(`Overall progress: ${totalProgress}/${divisor} = ${overallProgress}%`);
                      
                      return {
                        ...prev,
                        [analysisKey]: {
                          currentAgent: displayStatus,
                          completedAgents: newCompletedAgents,
                          totalAgents: selectedAgents.length,
                          progress: overallProgress,
                          agentProgresses: newAgentProgresses
                        }
                      };
                    });
                  }
                  
                  if (parsed.type === 'complete') {
                    // Analysis completed
                    setAnalysisProgress(prev => ({
                      ...prev,
                      [analysisKey]: {
                        ...prev[analysisKey],
                        currentAgent: 'Completed',
                        progress: 100
                      }
                    }));
                    
                    setAnalysisResults(prev => [
                      ...prev.filter(r => !(r.ticker === ticker && r.swarm === selectedSwarm)),
                      {
                        ticker,
                        swarm: selectedSwarm,
                        status: 'completed',
                        result: parsed.data,
                        timestamp: new Date(),
                        detailedAnalysis: {
                          decisions: parsed.data?.decisions,
                          analyst_signals: parsed.data?.analyst_signals,
                        },
                      }
                    ]);
                  }
                } catch (e) {
                  console.error('Error parsing SSE data:', e);
                }
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Error running analysis:', error);
      setAnalysisResults(prev => [
        ...prev.filter(r => !(r.ticker === ticker && r.swarm === selectedSwarm)),
        {
          ticker,
          swarm: selectedSwarm,
          status: 'error',
          timestamp: new Date(),
        }
      ]);
    } finally {
      setRunningAnalyses(prev => {
        const newSet = new Set(prev);
        newSet.delete(analysisKey);
        return newSet;
      });
      
      // Clean up progress tracking after a delay to show completion
      setTimeout(() => {
        setAnalysisProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[analysisKey];
          return newProgress;
        });
      }, 2000); // Show completion for 2 seconds
    }
  };

  const getAgentsForSwarm = (swarmName: string): string[] => {
    // Map swarm names to their agent IDs - these are sent to the backend
    const swarmAgents: Record<string, string[]> = {
      'Value Investors': ['ben_graham', 'charlie_munger', 'warren_buffett'],
      'Growth Investors': ['cathie_wood', 'peter_lynch', 'phil_fisher'],
      'Contrarian Investors': ['michael_burry', 'bill_ackman'],
      'Technical Analysis Team': ['technical_analyst', 'sentiment_analyst'],
      'Fundamental Analysis Team': ['fundamentals_analyst', 'valuation_analyst', 'aswath_damodaran'],
      'Macro Strategy Team': ['stanley_druckenmiller', 'rakesh_jhunjhunwala'],
      'All Agents': [
        'warren_buffett', 'charlie_munger', 'ben_graham', 'peter_lynch', 'phil_fisher',
        'cathie_wood', 'michael_burry', 'bill_ackman', 'stanley_druckenmiller',
        'rakesh_jhunjhunwala', 'aswath_damodaran', 'technical_analyst',
        'fundamentals_analyst', 'sentiment_analyst', 'valuation_analyst'
      ],
    };
    return swarmAgents[swarmName] || [];
  };

  const getExpectedProgressAgents = (swarmName: string): string[] => {
    // Map swarm names to expected agent names in progress events
    const progressAgents: Record<string, string[]> = {
      'Value Investors': ['ben_graham_agent', 'charlie_munger_agent', 'warren_buffett_agent', 'portfolio_manager', 'risk_management_agent'],
      'Growth Investors': ['cathie_wood_agent', 'peter_lynch_agent', 'phil_fisher_agent', 'portfolio_manager', 'risk_management_agent'],
      'Contrarian Investors': ['michael_burry_agent', 'bill_ackman_agent', 'portfolio_manager', 'risk_management_agent'],
      'Technical Analysis Team': ['technical_analyst_agent', 'sentiment_agent', 'portfolio_manager', 'risk_management_agent'],
      'Fundamental Analysis Team': ['fundamentals_analyst_agent', 'valuation_analyst_agent', 'aswath_damodaran_agent', 'portfolio_manager', 'risk_management_agent'],
      'Macro Strategy Team': ['stanley_druckenmiller_agent', 'rakesh_jhunjhunwala_agent', 'portfolio_manager', 'risk_management_agent'],
      'All Agents': [
        'warren_buffett_agent', 'charlie_munger_agent', 'ben_graham_agent', 'peter_lynch_agent', 'phil_fisher_agent',
        'cathie_wood_agent', 'michael_burry_agent', 'bill_ackman_agent', 'stanley_druckenmiller_agent',
        'rakesh_jhunjhunwala_agent', 'aswath_damodaran_agent', 'technical_analyst_agent',
        'fundamentals_analyst_agent', 'sentiment_agent', 'valuation_analyst_agent',
        'portfolio_manager', 'risk_management_agent'
      ],
    };
    return progressAgents[swarmName] || [];
  };

  const mapBackendAgentToSelected = (backendAgent: string): string | null => {
    // Map backend agent names back to selected agent names
    const mapping: Record<string, string> = {
      'ben_graham_agent': 'ben_graham',
      'charlie_munger_agent': 'charlie_munger',
      'warren_buffett_agent': 'warren_buffett',
      'cathie_wood_agent': 'cathie_wood',
      'peter_lynch_agent': 'peter_lynch',
      'phil_fisher_agent': 'phil_fisher',
      'michael_burry_agent': 'michael_burry',
      'bill_ackman_agent': 'bill_ackman',
      'technical_analyst_agent': 'technical_analyst',
      'sentiment_agent': 'sentiment_analyst',
      'fundamentals_analyst_agent': 'fundamentals_analyst',
      'valuation_analyst_agent': 'valuation_analyst',
      'aswath_damodaran_agent': 'aswath_damodaran',
      'stanley_druckenmiller_agent': 'stanley_druckenmiller',
      'rakesh_jhunjhunwala_agent': 'rakesh_jhunjhunwala',
      // portfolio_manager and risk_management_agent are not mapped (they're infrastructure)
    };
    return mapping[backendAgent] || null;
  };

  const getAnalysisStatus = (ticker: string) => {
    const analysisKey = `${ticker}-${selectedSwarm}`;
    const isRunning = runningAnalyses.has(analysisKey);
    const result = analysisResults.find(r => r.ticker === ticker && r.swarm === selectedSwarm);
    
    return { isRunning, result };
  };

  const getDateRange = () => {
    if (analysisDateRange === 'custom') {
      return {
        start_date: customStartDate,
        end_date: customEndDate || new Date().toISOString().split('T')[0]
      };
    }
    
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - parseInt(analysisDateRange));
    
    return {
      start_date: startDate.toISOString().split('T')[0],
      end_date: endDate.toISOString().split('T')[0]
    };
  };

  const getPositionValue = (position: PortfolioPosition) => {
    const longValue = position.long * position.long_cost_basis;
    const shortValue = position.short * position.short_cost_basis;
    return longValue - shortValue;
  };

  const getCurrentPrice = (ticker: string) => {
    // Look for current price in the latest analysis results
    const latestResult = analysisResults
      .filter(r => r.status === 'completed' && r.detailedAnalysis?.analyst_signals)
      .find(r => r.detailedAnalysis?.analyst_signals?.risk_management_agent?.[ticker]?.current_price);
    
    return latestResult?.detailedAnalysis?.analyst_signals?.risk_management_agent?.[ticker]?.current_price;
  };

  const calculatePriceChange = (currentPrice: number, costBasis: number) => {
    const change = currentPrice - costBasis;
    const changePercent = (change / costBasis) * 100;
    return { change, changePercent };
  };

  const calculateUnrealizedGains = (position: PortfolioPosition, currentPrice: number) => {
    if (!currentPrice) return { dollarGain: 0, percentGain: 0 };
    
    const longGain = position.long > 0 ? (currentPrice - position.long_cost_basis) * position.long : 0;
    const shortGain = position.short > 0 ? (position.short_cost_basis - currentPrice) * position.short : 0;
    const totalGain = longGain + shortGain;
    
    const totalCostBasis = (position.long * position.long_cost_basis) + (position.short * position.short_cost_basis);
    const percentGain = totalCostBasis > 0 ? (totalGain / totalCostBasis) * 100 : 0;
    
    return { dollarGain: totalGain, percentGain };
  };

  const getTotalUnrealizedGains = () => {
    if (!portfolio) return { totalGain: 0, totalPercent: 0 };
    
    let totalGain = 0;
    let totalCostBasis = 0;
    
    Object.entries(portfolio.positions)
      .filter(([, position]) => hasActivePositions(position))
      .forEach(([ticker, position]) => {
        const currentPrice = getCurrentPrice(ticker);
        if (currentPrice) {
          const { dollarGain } = calculateUnrealizedGains(position, currentPrice);
          totalGain += dollarGain;
          totalCostBasis += (position.long * position.long_cost_basis) + (position.short * position.short_cost_basis);
        }
      });
    
    const totalPercent = totalCostBasis > 0 ? (totalGain / totalCostBasis) * 100 : 0;
    return { totalGain, totalPercent };
  };

  const hasActivePositions = (position: PortfolioPosition) => {
    return position.long > 0 || position.short > 0;
  };

  const getAgentProgressEstimate = (agentName: string, status: string): number => {
    // Define progress stages for different agent types
    const progressMaps: Record<string, Record<string, number>> = {
      // Contrarian investors (Michael Burry, Bill Ackman)
      contrarian: {
        'Fetching financial metrics': 10,
        'Fetching line items': 15,
        'Gathering financial line items': 25,
        'Getting market cap': 30,
        'Fetching insider trades': 40,
        'Fetching company news': 50,
        'Analyzing business quality': 60,
        'Analyzing balance sheet and capital structure': 70,
        'Analyzing activism potential': 80,
        'Calculating intrinsic value & margin of safety': 85,
        'Generating': 95,
        'Done': 100
      },
      // Technical analysts
      technical: {
        'Fetching price data': 15,
        'Analyzing price data': 25,
        'Calculating trend signals': 40,
        'Calculating mean reversion': 55,
        'Calculating momentum': 70,
        'Analyzing volatility': 80,
        'Statistical analysis': 90,
        'Combining signals': 95,
        'Done': 100
      },
      // Sentiment analysts
      sentiment: {
        'Fetching insider trades': 20,
        'Analyzing trading patterns': 40,
        'Fetching company news': 60,
        'Combining signals': 80,
        'Done': 100
      },
      // Risk management
      risk: {
        'Fetching price data': 25,
        'Current price': 50,
        'Calculating position limits': 75,
        'Total portfolio value': 90,
        'Done': 100
      },
      // Portfolio manager
      portfolio: {
        'Processing analyst signals': 50,
        'Generating trading decisions': 80,
        'Done': 100
      },
      // Default for other agents
      default: {
        'Fetching': 20,
        'Analyzing': 50,
        'Calculating': 70,
        'Generating': 90,
        'Done': 100
      }
    };

    // Determine agent type
    let agentType = 'default';
    if (agentName.includes('michael_burry') || agentName.includes('bill_ackman')) {
      agentType = 'contrarian';
    } else if (agentName.includes('technical_analyst')) {
      agentType = 'technical';
    } else if (agentName.includes('sentiment_analyst')) {
      agentType = 'sentiment';
    } else if (agentName.includes('risk_management')) {
      agentType = 'risk';
    } else if (agentName.includes('portfolio_manager')) {
      agentType = 'portfolio';
    }

    const progressMap = progressMaps[agentType];
    
    // Find exact match first
    if (progressMap[status]) {
      return progressMap[status];
    }
    
    // Find partial match
    for (const [key, value] of Object.entries(progressMap)) {
      if (status.includes(key)) {
        return value;
      }
    }
    
    // Default based on common keywords
    if (status.includes('Fetching')) return 20;
    if (status.includes('Analyzing')) return 50;
    if (status.includes('Calculating')) return 70;
    if (status.includes('Generating')) return 90;
    if (status.includes('Done')) return 100;
    
    return 10; // Default for unknown status
  };

  return (
    <div className="p-6 space-y-6 bg-white min-h-screen">
      <div>
        <h1 className="text-3xl font-bold mb-2 text-gray-900">Portfolio Management</h1>
        <p className="text-gray-600">Create and manage your trading portfolio</p>
      </div>

      {!portfolio ? (
        <Card className="bg-white border-gray-200">
          <CardHeader>
            <CardTitle className="text-gray-900">Create New Portfolio</CardTitle>
            <CardDescription className="text-gray-600">Set up your initial portfolio with cash and tickers</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 bg-white">
            <div>
              <label className="block text-sm font-medium mb-2 text-gray-900">Initial Cash ($)</label>
              <Input
                type="number"
                value={initialCash}
                onChange={(e) => setInitialCash(e.target.value)}
                placeholder="100000"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2 text-gray-900">Margin Requirement</label>
              <Input
                type="number"
                step="0.1"
                value={marginRequirement}
                onChange={(e) => setMarginRequirement(e.target.value)}
                placeholder="0.5"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2 text-gray-900">Tickers (comma-separated)</label>
              <Input
                value={tickers}
                onChange={(e) => setTickers(e.target.value)}
                placeholder="AAPL,MSFT,GOOGL,TSLA"
                className="bg-white border-gray-300 text-gray-900"
              />
            </div>
            <Button onClick={createPortfolio} disabled={isLoading}>
              {isLoading ? 'Creating...' : 'Create Portfolio'}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Portfolio Overview */}
            <Card className="bg-white border-gray-200">
              <CardHeader>
                <CardTitle className="text-gray-900">Portfolio Overview</CardTitle>
              </CardHeader>
              <CardContent className="bg-white">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-700">Cash:</span>
                      <span className="font-medium text-gray-900">${portfolio.cash.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">Margin Requirement:</span>
                      <span className="font-medium text-gray-900">{(portfolio.margin_requirement * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-700">Margin Used:</span>
                      <span className="font-medium text-gray-900">${portfolio.margin_used.toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {(() => {
                      const { totalGain, totalPercent } = getTotalUnrealizedGains();
                      return (
                        <div className="bg-gray-50 rounded-lg p-3">
                          <div className="text-sm text-gray-600 mb-1">Total Unrealized Gains</div>
                          <div className={`text-lg font-bold ${totalGain >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {totalGain >= 0 ? '+' : ''}${totalGain.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </div>
                          <div className={`text-sm ${totalGain >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {totalGain >= 0 ? '+' : ''}{totalPercent.toFixed(2)}%
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* AI Analysis Controls */}
            <Card className="bg-white border-gray-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-gray-900">
                  <BarChart3 size={20} />
                  AI Analysis
                </CardTitle>
                <CardDescription className="text-gray-600">Run AI agent analysis on your holdings</CardDescription>
              </CardHeader>
              <CardContent className="bg-white">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-gray-900">Select Analysis Team</label>
                    <select 
                      value={selectedSwarm} 
                      onChange={(e) => setSelectedSwarm(e.target.value)}
                      className="w-full p-2 border border-gray-300 rounded-md bg-white text-gray-900"
                    >
                      {SWARM_NAMES.map((swarm) => (
                        <option key={swarm} value={swarm}>
                          {swarm}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2 text-gray-900">Select AI Model</label>
                    <select 
                      value={selectedModel.model_name} 
                      onChange={(e) => {
                        const model = apiModels.find(m => m.model_name === e.target.value);
                        if (model) setSelectedModel(model);
                      }}
                      className="w-full p-2 border border-gray-300 rounded-md bg-white text-gray-900"
                    >
                      {apiModels.map((model) => (
                        <option key={model.model_name} value={model.model_name}>
                          {model.display_name} ({model.provider})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2 text-gray-900">Analysis Time Range</label>
                    <select 
                      value={analysisDateRange} 
                      onChange={(e) => setAnalysisDateRange(e.target.value)}
                      className="w-full p-2 border border-gray-300 rounded-md bg-white text-gray-900"
                    >
                      <option value="7">Last 7 Days (Short-term)</option>
                      <option value="30">Last 30 Days (Default)</option>
                      <option value="90">Last 90 Days (Quarterly)</option>
                      <option value="252">Last 252 Days (1 Year)</option>
                      <option value="custom">Custom Date Range</option>
                    </select>
                  </div>
                  {analysisDateRange === 'custom' && (
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium mb-2 text-gray-900">Start Date</label>
                        <Input
                          type="date"
                          value={customStartDate}
                          onChange={(e) => setCustomStartDate(e.target.value)}
                          className="bg-white border-gray-300 text-gray-900"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-2 text-gray-900">End Date</label>
                        <Input
                          type="date"
                          value={customEndDate}
                          onChange={(e) => setCustomEndDate(e.target.value)}
                          className="bg-white border-gray-300 text-gray-900"
                        />
                      </div>
                    </div>
                  )}
                  <div className="text-sm text-gray-600">
                    Selected: <Badge variant="secondary">{selectedSwarm}</Badge>
                    <span className="mx-2">•</span>
                    <Badge variant="outline" className="text-gray-900">{selectedModel.display_name} ({selectedModel.provider})</Badge>
                    <span className="mx-2">•</span>
                    <Badge variant="outline" className="text-gray-900">
                      {analysisDateRange === 'custom' 
                        ? `${customStartDate || 'Start'} to ${customEndDate || 'Today'}` 
                        : `Last ${analysisDateRange} days`}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Current Positions with Analysis */}
          <Card className="bg-white border-gray-200">
            <CardHeader>
              <CardTitle className="text-gray-900">Current Positions & AI Analysis</CardTitle>
              <CardDescription className="text-gray-600">Your holdings with one-click AI analysis</CardDescription>
              {runningAnalyses.size > 0 && (
                <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-center gap-2 text-blue-800">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="font-medium">
                      Analysis in progress... Please wait before starting another analysis.
                    </span>
                  </div>
                </div>
              )}
            </CardHeader>
            <CardContent className="bg-white">
              <div className="space-y-3">
                {Object.entries(portfolio.positions)
                  .filter(([, position]) => hasActivePositions(position))
                  .map(([ticker, position]) => {
                    const { isRunning, result } = getAnalysisStatus(ticker);
                    const positionValue = getPositionValue(position);
                    const currentPrice = getCurrentPrice(ticker);
                    const { change, changePercent } = calculatePriceChange(currentPrice || 0, position.long_cost_basis);
                    const { dollarGain, percentGain } = calculateUnrealizedGains(position, currentPrice || 0);
                    
                    return (
                      <div key={ticker} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg bg-white">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <span className="font-bold text-lg text-gray-900">{ticker}</span>
                            {currentPrice && (
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-gray-900">
                                  ${currentPrice.toFixed(2)}
                                </Badge>
                                {position.long > 0 && currentPrice && (
                                  <Badge 
                                    variant="outline" 
                                    className={`text-xs ${change >= 0 ? 'text-green-700 bg-green-50 border-green-200' : 'text-red-700 bg-red-50 border-red-200'}`}
                                  >
                                    {change >= 0 ? "+" : ""}{changePercent.toFixed(1)}%
                                  </Badge>
                                )}
                              </div>
                            )}
                            {/* Unrealized Gains + Current Value Display */}
                            {dollarGain !== 0 && currentPrice && (
                              <Badge 
                                variant="outline" 
                                className={`font-semibold ${dollarGain >= 0 ? 'text-green-700 bg-green-50 border-green-200' : 'text-red-700 bg-red-50 border-red-200'}`}
                              >
                                {dollarGain >= 0 ? '+' : ''}${dollarGain.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                <span className="ml-1 text-xs">
                                  ({dollarGain >= 0 ? '+' : ''}{percentGain.toFixed(1)}%)
                                </span>
                                <span className="ml-2 text-xs font-normal">
                                  Current: ${(position.long * currentPrice).toLocaleString()}
                                </span>
                              </Badge>
                            )}
                            {/* Original Cost Basis Value */}
                            <Badge variant="outline" className="text-gray-700 bg-gray-50 border-gray-200">
                              Original: ${Math.abs(positionValue).toLocaleString()}
                            </Badge>
                          </div>
                          <div className="text-sm text-gray-600 space-y-1">
                            {position.long > 0 && (
                              <div className="flex items-center justify-between">
                                <span>Long: {position.long} shares @ ${position.long_cost_basis}</span>
                              </div>
                            )}
                            {position.short > 0 && (
                              <div>Short: {position.short} shares @ ${position.short_cost_basis}</div>
                            )}
                          </div>
                          {result && (
                            <div className="mt-2">
                              <Badge 
                                variant={result.status === 'completed' ? 'success' : 'destructive'}
                                className="text-xs"
                              >
                                Last Analysis: {result.swarm} - {result.status}
                              </Badge>
                              {result.status === 'completed' && result.detailedAnalysis && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="ml-2 text-xs"
                                  onClick={() => setViewingResult(result)}
                                >
                                  View Results
                                </Button>
                              )}
                            </div>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            onClick={() => runAnalysisForTicker(ticker)}
                            disabled={runningAnalyses.size > 0}
                            className="min-w-[120px]"
                          >
                            {isRunning ? (
                              <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Analyzing...
                              </>
                            ) : runningAnalyses.size > 0 ? (
                              <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Analysis Running...
                              </>
                            ) : (
                              <>
                                <Play className="w-4 h-4 mr-2" />
                                Run Analysis
                              </>
                            )}
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                
                {/* Progress bars for running analyses */}
                {Object.entries(analysisProgress).map(([analysisKey, progress]) => {
                  const [tickerFromKey] = analysisKey.split('-');
                  return (
                    <div key={`progress-${analysisKey}`} className="border border-blue-200 rounded-lg p-4 bg-blue-50">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-blue-900">{tickerFromKey}</span>
                          <Badge variant="outline" className="text-blue-700 bg-blue-100 border-blue-300">
                            {progress.progress}%
                          </Badge>
                        </div>
                      </div>
                      
                      {/* Current status - now full width */}
                      <div className="text-sm text-blue-800 mb-2 font-medium">
                        {progress.currentAgent}
                      </div>
                      
                      {/* Progress bar */}
                      <div className="w-full bg-blue-200 rounded-full h-3 mb-3">
                        <div 
                          className="bg-blue-600 h-3 rounded-full transition-all duration-500 ease-out flex items-center justify-end pr-2"
                          style={{ width: `${progress.progress}%` }}
                        >
                          {progress.progress > 15 && (
                            <span className="text-xs text-white font-medium">
                              {progress.progress}%
                            </span>
                          )}
                        </div>
                      </div>
                      
                      {/* Agent completion status */}
                      <div className="flex items-center justify-between text-xs text-blue-600">
                        <span>
                          {progress.completedAgents.length} of {progress.totalAgents} agents completed
                        </span>
                        {progress.completedAgents.length > 0 && (
                          <span className="text-xs bg-blue-100 px-2 py-1 rounded">
                            ✓ {progress.completedAgents.slice(-1)[0]} finished
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Empty state */}
                {Object.entries(portfolio.positions).filter(([, position]) => hasActivePositions(position)).length === 0 && 
                 Object.keys(analysisProgress).length === 0 && (
                  <div className="text-center py-8 text-gray-500">
                    No active positions found. Add some positions below to get started.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Add Position */}
          <Card className="bg-white border-gray-200">
            <CardHeader>
              <CardTitle className="text-gray-900">Add/Update Position</CardTitle>
            </CardHeader>
            <CardContent className="bg-white">
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900">Ticker</label>
                  <Input
                    value={newPosition.ticker}
                    onChange={(e) => setNewPosition({ ...newPosition, ticker: e.target.value.toUpperCase() })}
                    placeholder="AAPL"
                    className="bg-white border-gray-300 text-gray-900"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900">Long Shares</label>
                  <Input
                    type="number"
                    value={newPosition.long_shares}
                    onChange={(e) => setNewPosition({ ...newPosition, long_shares: parseInt(e.target.value) || 0 })}
                    className="bg-white border-gray-300 text-gray-900"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900">Long Cost Basis</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={newPosition.long_cost_basis}
                    onChange={(e) => setNewPosition({ ...newPosition, long_cost_basis: parseFloat(e.target.value) || 0 })}
                    className="bg-white border-gray-300 text-gray-900"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900">Short Shares</label>
                  <Input
                    type="number"
                    value={newPosition.short_shares}
                    onChange={(e) => setNewPosition({ ...newPosition, short_shares: parseInt(e.target.value) || 0 })}
                    className="bg-white border-gray-300 text-gray-900"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-900">Short Cost Basis</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={newPosition.short_cost_basis}
                    onChange={(e) => setNewPosition({ ...newPosition, short_cost_basis: parseFloat(e.target.value) || 0 })}
                    className="bg-white border-gray-300 text-gray-900"
                  />
                </div>
              </div>
              <Button onClick={updatePosition} className="mt-4" disabled={!newPosition.ticker}>
                Update Position
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Analysis Results Modal */}
      {viewingResult && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl max-h-[80vh] overflow-y-auto m-4">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-gray-900">
                Analysis Results: {viewingResult.ticker}
              </h2>
              <Button
                variant="ghost"
                onClick={() => setViewingResult(null)}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </Button>
            </div>
            
            <div className="space-y-4">
              <div className="flex gap-2 mb-4">
                <Badge variant="secondary">{viewingResult.swarm}</Badge>
                <Badge variant="outline">{viewingResult.timestamp.toLocaleString()}</Badge>
              </div>
              
              {/* Trading Decisions Section */}
              {viewingResult.detailedAnalysis?.decisions && (
                <Card className="bg-white border-gray-200">
                  <CardHeader>
                    <CardTitle className="text-gray-900 flex items-center gap-2">
                      <Target className="w-5 h-5 text-blue-500" />
                      Trading Decisions
                    </CardTitle>
                    <CardDescription>AI-recommended actions for your portfolio</CardDescription>
                  </CardHeader>
                  <CardContent className="bg-white">
                    <div className="space-y-4">
                      {Object.entries(viewingResult.detailedAnalysis.decisions as Record<string, TradingDecision>).map(([ticker, decision], index) => (
                        <div 
                          key={ticker} 
                          className="border border-gray-200 rounded-lg p-4 bg-gradient-to-r from-gray-50 to-white hover:shadow-md transition-all duration-300 animate-in fade-in slide-in-from-left"
                          style={{ animationDelay: `${index * 100}ms` }}
                        >
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <span className="font-bold text-xl text-gray-900">{ticker}</span>
                              {/* Show current price if available from risk management agent */}
                              {viewingResult.detailedAnalysis?.analyst_signals?.risk_management_agent?.[ticker]?.current_price && (
                                <Badge variant="outline" className="text-gray-900 font-semibold">
                                  ${viewingResult.detailedAnalysis.analyst_signals.risk_management_agent[ticker].current_price.toFixed(2)}
                                </Badge>
                              )}
                              <div className="flex items-center gap-2">
                                {decision.action === 'buy' && <TrendingUp className="w-4 h-4 text-green-600 animate-pulse" />}
                                {decision.action === 'sell' && <TrendingDown className="w-4 h-4 text-red-600 animate-pulse" />}
                                {decision.action === 'hold' && <Minus className="w-4 h-4 text-gray-600" />}
                                <Badge 
                                  variant="outline"
                                  className={`animate-in zoom-in duration-300 ${
                                    decision.action === 'buy' ? 'text-green-700 bg-green-50 border-green-200' : 
                                    decision.action === 'sell' ? 'text-red-700 bg-red-50 border-red-200' : 
                                    'text-gray-700 bg-gray-50 border-gray-200'
                                  }`}
                                >
                                  {decision.action?.toUpperCase()}
                                </Badge>
                              </div>
                              {decision.quantity > 0 && (
                                <Badge variant="outline" className="animate-in slide-in-from-right duration-300">
                                  {decision.quantity} shares
                                  {/* Show trade value if price is available */}
                                  {viewingResult.detailedAnalysis?.analyst_signals?.risk_management_agent?.[ticker]?.current_price && (
                                    <span className="ml-1 text-xs">
                                      (${(decision.quantity * viewingResult.detailedAnalysis.analyst_signals.risk_management_agent[ticker].current_price).toLocaleString()})
                                    </span>
                                  )}
                                </Badge>
                              )}
                            </div>
                            {decision.confidence > 0 && (
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-sm text-gray-700">
                                  {decision.confidence.toFixed(1)}% confidence
                                </Badge>
                                {decision.confidence > 70 && <AlertTriangle className="w-4 h-4 text-orange-500" />}
                              </div>
                            )}
                          </div>
                          
                          {/* Confidence Progress Bar */}
                          {decision.confidence > 0 && (
                            <div className="mb-3">
                              <div className="flex justify-between text-xs text-gray-600 mb-1">
                                <span>Confidence Level</span>
                                <span>{decision.confidence.toFixed(1)}%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                                <div 
                                  className={`h-2 rounded-full transition-all duration-1000 ease-out ${
                                    decision.confidence >= 70 ? 'bg-green-600' :
                                    decision.confidence >= 50 ? 'bg-yellow-500' :
                                    'bg-red-600'
                                  }`}
                                  style={{ 
                                    width: `${decision.confidence}%`,
                                    animationDelay: `${index * 100 + 200}ms`
                                  }}
                                />
                              </div>
                            </div>
                          )}
                          
                          <div className="bg-white rounded-lg p-3 border-l-4 border-l-blue-500">
                            <p className="text-sm text-gray-700 leading-relaxed">{decision.reasoning}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* Analyst Signals Section */}
              {viewingResult.detailedAnalysis?.analyst_signals && (
                <Card className="bg-white border-gray-200">
                  <CardHeader>
                    <CardTitle className="text-gray-900 flex items-center gap-2">
                      <BarChart3 className="w-5 h-5 text-purple-500" />
                      Analyst Signals
                    </CardTitle>
                    <CardDescription>Detailed analysis from AI agents</CardDescription>
                  </CardHeader>
                  <CardContent className="bg-white">
                    <div className="space-y-6">
                      {Object.entries(viewingResult.detailedAnalysis.analyst_signals as Record<string, Record<string, AnalystSignal>>).map(([agentName, agentData], agentIndex) => (
                        <div 
                          key={agentName} 
                          className="border border-gray-200 rounded-lg p-4 animate-in fade-in slide-in-from-bottom hover:shadow-sm transition-all duration-300"
                          style={{ animationDelay: `${agentIndex * 150}ms` }}
                        >
                          <h4 className="font-semibold text-gray-900 mb-3 capitalize flex items-center gap-2">
                            {agentName === 'technical_analyst_agent' && <TrendingUp className="w-4 h-4 text-blue-500" />}
                            {agentName === 'sentiment_agent' && <Target className="w-4 h-4 text-green-500" />}
                            {agentName === 'risk_management_agent' && <AlertTriangle className="w-4 h-4 text-orange-500" />}
                            {agentName.replace(/_/g, ' ').replace(' agent', '')} Analysis
                          </h4>
                          <div className="space-y-3">
                            {Object.entries(agentData).map(([ticker, analysis], tickerIndex) => (
                              <div 
                                key={ticker} 
                                className="bg-gradient-to-r from-gray-50 to-white rounded-lg p-3 border border-gray-100 animate-in slide-in-from-left"
                                style={{ animationDelay: `${agentIndex * 150 + tickerIndex * 50}ms` }}
                              >
                                <div className="flex items-center gap-3 mb-2">
                                  <span className="font-medium text-gray-900">{ticker}</span>
                                  {analysis.signal && (
                                    <div className="flex items-center gap-2">
                                      {analysis.signal === 'bullish' && <TrendingUp className="w-3 h-3 text-green-600" />}
                                      {analysis.signal === 'bearish' && <TrendingDown className="w-3 h-3 text-red-600" />}
                                      {analysis.signal === 'neutral' && <Minus className="w-3 h-3 text-gray-600" />}
                                      <Badge 
                                        variant="outline"
                                        className={
                                          analysis.signal === 'bullish' ? 'text-green-700 bg-green-50 border-green-200' :
                                          analysis.signal === 'bearish' ? 'text-red-700 bg-red-50 border-red-200' :
                                          'text-gray-700 bg-gray-50 border-gray-200'
                                        }
                                      >
                                        {analysis.signal}
                                      </Badge>
                                    </div>
                                  )}
                                  {analysis.confidence && (
                                    <Badge variant="outline" className="animate-in slide-in-from-right duration-300">
                                      {analysis.confidence}% confidence
                                    </Badge>
                                  )}
                                </div>
                                
                                {/* Confidence bar for analyst signals */}
                                {analysis.confidence && analysis.confidence > 0 && (
                                  <div className="mb-2">
                                    <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                                      <div 
                                        className={`h-1.5 rounded-full transition-all duration-1000 ease-out ${
                                          analysis.confidence >= 70 ? 'bg-green-600' :
                                          analysis.confidence >= 50 ? 'bg-yellow-500' :
                                          'bg-red-600'
                                        }`}
                                        style={{ 
                                          width: `${analysis.confidence}%`,
                                          animationDelay: `${agentIndex * 150 + tickerIndex * 50 + 200}ms`
                                        }}
                                      />
                                    </div>
                                  </div>
                                )}
                                
                                {/* Display reasoning if available */}
                                {analysis.reasoning && (
                                  <div className="text-sm text-gray-700 mb-2">
                                    {typeof analysis.reasoning === 'string' ? (
                                      <p>{analysis.reasoning}</p>
                                    ) : (
                                      <div>
                                        <p className="font-medium mb-1">Portfolio Analysis:</p>
                                        <div className="text-xs space-y-1 bg-white rounded p-2">
                                          {Object.entries(analysis.reasoning).map(([key, value]) => (
                                            <div key={key} className="flex justify-between">
                                              <span className="capitalize">{key.replace(/_/g, ' ')}:</span>
                                              <span>${typeof value === 'number' ? value.toLocaleString() : value}</span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )}
                                
                                {/* Display risk management info */}
                                {analysis.remaining_position_limit && (
                                  <div className="text-sm text-gray-600 space-y-1">
                                    {analysis.current_price && (
                                      <div className="flex justify-between items-center mb-2 p-2 bg-blue-50 rounded">
                                        <span className="font-medium text-blue-900">Current Price:</span>
                                        <span className="font-bold text-blue-900">${analysis.current_price}</span>
                                      </div>
                                    )}
                                    <div>Position Limit: ${analysis.remaining_position_limit.toLocaleString()}</div>
                                    {analysis.current_price && (
                                      <div>Max Shares: {Math.floor(analysis.remaining_position_limit / analysis.current_price).toLocaleString()}</div>
                                    )}
                                  </div>
                                )}
                                
                                {/* Display strategy signals for technical analysis */}
                                {analysis.strategy_signals && (
                                  <div className="mt-2">
                                    <p className="text-xs font-medium text-gray-700 mb-1">Strategy Breakdown:</p>
                                    <div className="grid grid-cols-2 gap-2 text-xs">
                                      {Object.entries(analysis.strategy_signals).map(([strategy, data]) => (
                                        <div key={strategy} className="bg-white rounded p-2">
                                          <div className="font-medium text-gray-800 capitalize">
                                            {strategy.replace(/_/g, ' ')}
                                          </div>
                                          <div className="flex gap-2">
                                            <Badge 
                                              variant="outline"
                                              className={
                                                data.signal === 'bullish' ? 'text-green-700 bg-green-50 border-green-200' :
                                                data.signal === 'bearish' ? 'text-red-700 bg-red-50 border-red-200' :
                                                'text-gray-700 bg-gray-50 border-gray-200'
                                              }
                                            >
                                              {data.signal}
                                            </Badge>
                                            <span className="text-gray-600">{data.confidence}%</span>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* Portfolio Context Section */}
              {portfolio && (
                <Card className="bg-white border-gray-200">
                  <CardHeader>
                    <CardTitle className="text-gray-900">💼 Portfolio Context</CardTitle>
                    <CardDescription>Current portfolio state used for analysis</CardDescription>
                  </CardHeader>
                  <CardContent className="bg-white">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      <div className="bg-gray-50 rounded p-3">
                        <div className="text-sm text-gray-600">Available Cash</div>
                        <div className="text-lg font-semibold text-gray-900">${portfolio.cash.toLocaleString()}</div>
                      </div>
                      <div className="bg-gray-50 rounded p-3">
                        <div className="text-sm text-gray-600">Margin Used</div>
                        <div className="text-lg font-semibold text-gray-900">${portfolio.margin_used.toLocaleString()}</div>
                      </div>
                      <div className="bg-gray-50 rounded p-3">
                        <div className="text-sm text-gray-600">Margin Requirement</div>
                        <div className="text-lg font-semibold text-gray-900">{(portfolio.margin_requirement * 100).toFixed(1)}%</div>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <h5 className="font-medium text-gray-900">Current Positions</h5>
                      {Object.entries(portfolio.positions)
                        .filter(([, position]) => hasActivePositions(position))
                        .map(([ticker, position]) => (
                          <div key={ticker} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                            <span className="font-medium text-gray-900">{ticker}</span>
                            <div className="text-sm text-gray-600">
                              {position.long > 0 && <span>Long: {position.long} @ ${position.long_cost_basis}</span>}
                              {position.short > 0 && <span>Short: {position.short} @ ${position.short_cost_basis}</span>}
                            </div>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 