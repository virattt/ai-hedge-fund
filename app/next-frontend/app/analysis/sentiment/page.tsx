// app/next-frontend/app/analysis/sentiment/page.tsx
"use client";
import AnalysisPageLayout from '@/components/analysis/analysis-page-layout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import React, { useState } from 'react';

export default function SentimentAnalysisPage() {
  const [dataSource, setDataSource] = useState('');
  const inputControls = (
    <>
      <div>
        <Label htmlFor="data-source-sentiment">Data Source</Label>
        <Input id="data-source-sentiment" value={dataSource} onChange={(e) => setDataSource(e.target.value)} placeholder="e.g., News headlines, Twitter" />
      </div>
      <Button onClick={() => alert(`Sentiment analysis for ${dataSource} would run here.`)} disabled={!dataSource}>Run Analysis</Button>
    </>
  );
  const resultsDisplay = <p>Sentiment analysis results (e.g., sentiment scores, trends) will appear here.</p>;

  return (
    <AnalysisPageLayout
      title="Sentiment Analysis"
      description="Analyze market sentiment from news, social media, and other sources."
      inputControls={inputControls}
      resultsDisplay={resultsDisplay}
    />
  );
}
