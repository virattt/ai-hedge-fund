import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { HoldingCreate } from '@/types/holdings';
import { useState } from 'react';

interface HoldingFormProps {
  onSubmit: (data: HoldingCreate) => void;
  onCancel: () => void;
  initialData?: Partial<HoldingCreate>;
  submitLabel?: string;
}

const SECTORS = [
  'Technology', 'Healthcare', 'Financial Services', 'Consumer Cyclical',
  'Industrials', 'Energy', 'Utilities', 'Real Estate', 'Communication Services',
  'Consumer Defensive', 'Basic Materials', 'Bonds', 'Index Fund', 'Mixed/Multi-Asset',
];

export function HoldingForm({ onSubmit, onCancel, initialData, submitLabel = 'Add Holding' }: HoldingFormProps) {
  const [ticker, setTicker] = useState(initialData?.ticker || '');
  const [investmentName, setInvestmentName] = useState(initialData?.investment_name || '');
  const [quantity, setQuantity] = useState(initialData?.quantity?.toString() || '');
  const [buyPrice, setBuyPrice] = useState(initialData?.buy_price?.toString() || '');
  const [currency, setCurrency] = useState(initialData?.currency || 'GBP');
  const [portfolioName, setPortfolioName] = useState(initialData?.portfolio_name || 'Default');
  const [sector, setSector] = useState(initialData?.sector || '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      ticker: ticker.toUpperCase().trim(),
      investment_name: investmentName.trim(),
      quantity: parseFloat(quantity),
      buy_price: parseFloat(buyPrice),
      currency: currency.toUpperCase().trim(),
      portfolio_name: portfolioName.trim(),
      sector: sector || undefined,
    });
  };

  const isValid = ticker.trim() && investmentName.trim() && parseFloat(quantity) > 0 && parseFloat(buyPrice) > 0;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Ticker / Symbol</label>
          <Input value={ticker} onChange={e => setTicker(e.target.value)} placeholder="e.g. VUSA" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Portfolio Name</label>
          <Input value={portfolioName} onChange={e => setPortfolioName(e.target.value)} placeholder="Default" />
        </div>
      </div>
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Investment Name</label>
        <Input value={investmentName} onChange={e => setInvestmentName(e.target.value)} placeholder="e.g. Vanguard S&P 500 ETF" />
      </div>
      <div className="grid grid-cols-4 gap-4">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Quantity</label>
          <Input type="number" step="any" min="0" value={quantity} onChange={e => setQuantity(e.target.value)} placeholder="0" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Buy Price</label>
          <Input type="number" step="any" min="0" value={buyPrice} onChange={e => setBuyPrice(e.target.value)} placeholder="0.00" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Currency</label>
          <Input value={currency} onChange={e => setCurrency(e.target.value)} placeholder="GBP" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Sector</label>
          <select
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            value={sector}
            onChange={e => setSector(e.target.value)}
          >
            <option value="">Select sector...</option>
            {SECTORS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
        <Button type="submit" size="sm" disabled={!isValid}>{submitLabel}</Button>
      </div>
    </form>
  );
}
