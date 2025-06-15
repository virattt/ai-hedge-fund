// app/next-frontend/app/dashboard/page.tsx
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowRight } from 'lucide-react';

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">Welcome to the Financial Analysis Platform!</h1>
        <p className="text-muted-foreground mt-2">
          Your central hub for interacting with financial agents, performing in-depth data analysis, and managing your investment portfolio.
        </p>
      </section>

      <section className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Explore Financial Agents</CardTitle>
            <CardDescription>Get insights from various investment philosophies.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Interact with AI agents representing famous investors like Warren Buffett, Peter Lynch, and more.</p>
          </CardContent>
          <CardFooter>
            <Button asChild variant="outline">
              <Link href="/agents">Go to Agents <ArrowRight className="ml-2 h-4 w-4" /></Link>
            </Button>
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>In-Depth Data Analysis</CardTitle>
            <CardDescription>Utilize powerful tools for market evaluation.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Perform fundamental, technical, sentiment, and valuation analysis to make informed decisions.</p>
          </CardContent>
          <CardFooter>
            <Button asChild variant="outline">
              <Link href="/analysis">Go to Analysis <ArrowRight className="ml-2 h-4 w-4" /></Link>
            </Button>
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Portfolio Management</CardTitle>
            <CardDescription>Track and backtest your investment strategies.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Manage your assets, monitor performance, and simulate historical returns with our backtester.</p>
          </CardContent>
          <CardFooter>
            <Button asChild variant="outline">
              <Link href="/portfolio">Go to Portfolio <ArrowRight className="ml-2 h-4 w-4" /></Link>
            </Button>
          </CardFooter>
        </Card>
      </section>

      <section>
        <Card className="bg-secondary">
          <CardHeader>
            <CardTitle>Initial Setup Guide</CardTitle>
            <CardDescription>Configure the platform for self-hosted use.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Follow our step-by-step guide to get all features of this repository configured for a completely free and self-hosted experience.</p>
          </CardContent>
          <CardFooter>
            <Button asChild>
              <Link href="/setup-guide">Start Setup Guide <ArrowRight className="ml-2 h-4 w-4" /></Link>
            </Button>
          </CardFooter>
        </Card>
      </section>

      {/* Placeholder for future: Recent Activity/Updates */}
    </div>
  );
}
