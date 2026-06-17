import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useState } from 'react';

interface CsvImporterProps {
  onImport: (csvText: string, portfolioName: string) => void;
  onCancel: () => void;
}

export function CsvImporter({ onImport, onCancel }: CsvImporterProps) {
  const [csvText, setCsvText] = useState('');
  const [portfolioName, setPortfolioName] = useState('Default');

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Portfolio Name</label>
        <Input value={portfolioName} onChange={e => setPortfolioName(e.target.value)} placeholder="Default" />
      </div>
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">
          Paste CSV / tab-separated holdings (from AJ Bell or similar)
        </label>
        <textarea
          className="w-full h-48 rounded-md border border-input bg-background px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
          value={csvText}
          onChange={e => setCsvText(e.target.value)}
          placeholder={`Ticker, Investment Name, Quantity, Buy Price, Cost, Currency\nVUSA, Vanguard S&P 500 ETF, 100, 52.30, 5230.00, GBP\nSMT, Scottish Mortgage Trust, 50, 8.45, 422.50, GBP`}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Supports comma or tab separated values. Header row is auto-detected.
        Minimum columns: Ticker, Name, Quantity, Buy Price.
      </p>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
        <Button size="sm" disabled={!csvText.trim()} onClick={() => onImport(csvText, portfolioName)}>
          Import Holdings
        </Button>
      </div>
    </div>
  );
}
