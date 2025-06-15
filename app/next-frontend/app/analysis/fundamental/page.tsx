// app/next-frontend/app/analysis/fundamental/page.tsx
"use client"; // This page will have interactive elements

import React, { useState } from 'react';
import AnalysisPageLayout from '@/components/analysis/analysis-page-layout';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label'; // To be created if not exists
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'; // To be created

export default function FundamentalAnalysisPage() {
  const [ticker, setTicker] = useState('');
  const [analysisPeriod, setAnalysisPeriod] = useState('annual');
  const [results, setResults] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleRunAnalysis = () => {
    if (!ticker) {
      alert('Please enter a stock ticker.');
      return;
    }
    setIsLoading(true);
    setResults(null);
    // Simulate API call
    setTimeout(() => {
      setResults(`Fundamental analysis results for ${ticker} (${analysisPeriod}):
- P/E Ratio: 15
- Debt/Equity: 0.5
- Revenue Growth (YoY): 10%`);
      setIsLoading(false);
    }, 1500);
  };

  const inputControls = (
    <>
      <div>
        <Label htmlFor="ticker">Stock Ticker</Label>
        <Input
          id="ticker"
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="e.g., AAPL"
        />
      </div>
      <div>
        <Label htmlFor="period">Analysis Period</Label>
        <Select value={analysisPeriod} onValueChange={setAnalysisPeriod}>
          <SelectTrigger id="period">
            <SelectValue placeholder="Select period" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="annual">Annual</SelectItem>
            <SelectItem value="quarterly">Quarterly</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <Button onClick={handleRunAnalysis} disabled={isLoading || !ticker}>
        {isLoading ? 'Analyzing...' : 'Run Analysis'}
      </Button>
    </>
  );

  const resultsDisplay = (
    results ? <pre className="whitespace-pre-wrap">{results}</pre> : <p>Enter a ticker and run analysis to see results.</p>
  );

  return (
    <AnalysisPageLayout
      title="Fundamental Analysis"
      description="Evaluate a company's intrinsic value by examining its financial statements and economic factors."
      inputControls={inputControls}
      resultsDisplay={resultsDisplay}
      isResultsLoading={isLoading}
    />
  );
}
