// app/next-frontend/app/portfolio/page.tsx
"use client"; // For potential future interactive elements

import HoldingsTable from '@/components/portfolio/holdings-table';
import BacktestSetup from '@/components/portfolio/backtest-setup';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { DollarSign, TrendingUp, History } from 'lucide-react'; // Example Icons

export default function PortfolioPage() {
  const mockPortfolioValue = 5000.00; // Example value
  const mockPortfolioReturn = 15.5; // Example value

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Portfolio Management</h1>
        <p className="text-muted-foreground mt-2">
          Track your investments, analyze performance, and backtest your strategies.
        </p>
      </div>

      <section className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Portfolio Value</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${mockPortfolioValue.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground">+{mockPortfolioReturn.toFixed(2)}% since last month</p>
          </CardContent>
        </Card>
        {/* Add more summary cards if needed, e.g., Best Performer, Worst Performer */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Overall Return</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">+{mockPortfolioReturn.toFixed(2)}%</div>
            <p className="text-xs text-muted-foreground">All-time return on investment</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
            <History className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">3 Trades</div>
            <p className="text-xs text-muted-foreground">In the last 7 days</p>
          </CardContent>
        </Card>
      </section>

      <section>
        <Card>
          <CardHeader>
            <CardTitle>Current Holdings</CardTitle>
            <CardDescription>Overview of assets currently in your portfolio.</CardDescription>
          </CardHeader>
          <CardContent>
            <HoldingsTable />
          </CardContent>
        </Card>
      </section>

      <section>
        <BacktestSetup />
      </section>
    </div>
  );
}
