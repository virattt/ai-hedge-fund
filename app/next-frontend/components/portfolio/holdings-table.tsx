// app/next-frontend/components/portfolio/holdings-table.tsx
"use client"; // May need client features for interactions later

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"; // To be created if not exists

export interface Holding {
  id: string;
  name: string;
  ticker: string;
  quantity: number;
  currentPrice: number;
  totalValue: number;
  allocation: number; // Percentage
}

const mockHoldings: Holding[] = [
  { id: '1', name: 'Apple Inc.', ticker: 'AAPL', quantity: 10, currentPrice: 170.00, totalValue: 1700.00, allocation: 34 },
  { id: '2', name: 'Microsoft Corp.', ticker: 'MSFT', quantity: 5, currentPrice: 300.00, totalValue: 1500.00, allocation: 30 },
  { id: '3', name: 'Google LLC', ticker: 'GOOGL', quantity: 8, currentPrice: 150.00, totalValue: 1200.00, allocation: 24 },
  { id: '4', name: 'Amazon.com Inc.', ticker: 'AMZN', quantity: 2, currentPrice: 300.00, totalValue: 600.00, allocation: 12 },
];

// Calculate total portfolio value for allocation percentage (if not pre-calculated)
// const totalPortfolioValue = mockHoldings.reduce((sum, holding) => sum + holding.totalValue, 0);

export default function HoldingsTable() {
  return (
    <Table>
      <TableCaption>A list of your current portfolio holdings.</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Asset Name</TableHead>
          <TableHead>Ticker</TableHead>
          <TableHead className="text-right">Quantity</TableHead>
          <TableHead className="text-right">Current Price</TableHead>
          <TableHead className="text-right">Total Value</TableHead>
          <TableHead className="text-right">Allocation</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {mockHoldings.map((holding) => (
          <TableRow key={holding.id}>
            <TableCell className="font-medium">{holding.name}</TableCell>
            <TableCell>{holding.ticker}</TableCell>
            <TableCell className="text-right">{holding.quantity}</TableCell>
            <TableCell className="text-right">${holding.currentPrice.toFixed(2)}</TableCell>
            <TableCell className="text-right">${holding.totalValue.toFixed(2)}</TableCell>
            <TableCell className="text-right">{holding.allocation.toFixed(2)}%</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
