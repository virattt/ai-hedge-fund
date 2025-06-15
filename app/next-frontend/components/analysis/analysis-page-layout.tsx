// app/next-frontend/components/analysis/analysis-page-layout.tsx
import React from 'react';

interface AnalysisPageLayoutProps {
  title: string;
  description: string;
  inputControls: React.ReactNode;
  resultsDisplay: React.ReactNode;
  isResultsLoading?: boolean; // Optional: for loading state
}

export default function AnalysisPageLayout({
  title,
  description,
  inputControls,
  resultsDisplay,
  isResultsLoading = false,
}: AnalysisPageLayoutProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
        <p className="text-muted-foreground mt-2">{description}</p>
      </div>

      <div className="grid gap-8 md:grid-cols-3">
        <div className="md:col-span-1">
          <h2 className="text-xl font-semibold mb-4">Controls</h2>
          <div className="space-y-4">
            {inputControls}
          </div>
        </div>
        <div className="md:col-span-2">
          <h2 className="text-xl font-semibold mb-4">Results</h2>
          {isResultsLoading ? (
            <div className="flex items-center justify-center h-64">
              {/* Add a ShadCN Spinner or a simple loading text */}
              <p>Loading results...</p>
            </div>
          ) : (
            <div className="p-4 border rounded-md min-h-[200px] bg-muted/30">
              {resultsDisplay}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
