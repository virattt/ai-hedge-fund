import { useEffect, useState } from 'react';

interface PairSelectorProps {
  value: string;
  onChange: (pair: string) => void;
}

export function PairSelector({ value, onChange }: PairSelectorProps) {
  const [pairs, setPairs] = useState<string[]>([]);

  useEffect(() => {
    async function fetchPairs() {
      try {
        const res = await fetch(
          'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1'
        );
        const data = await res.json();
        setPairs(data.map((c: any) => `${c.symbol.toUpperCase()}/USDT`));
      } catch (e) {
        console.error('Failed to fetch coin list', e);
      }
    }
    fetchPairs();
  }, []);

  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="p-1 border rounded">
      {pairs.map((p) => (
        <option key={p} value={p}>
          {p}
        </option>
      ))}
    </select>
  );
}
