// app/next-frontend/app/analysis/page.tsx
import Link from 'next/link';
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowRight, BarChart, LineChart, SearchCheck, ShoppingCart } from 'lucide-react'; // Example icons

const analysisTypes = [
  { name: 'Fundamental Analysis', href: '/analysis/fundamental', description: 'Evaluate a company\'s intrinsic value by examining related economic and financial factors.', icon: <BarChart className="h-8 w-8 mb-2 text-primary" /> },
  { name: 'Technical Analysis', href: '/analysis/technical', description: 'Forecast the direction of prices through the study of past market data, primarily price and volume.', icon: <LineChart className="h-8 w-8 mb-2 text-primary" /> },
  { name: 'Sentiment Analysis', href: '/analysis/sentiment', description: 'Analyze market sentiment from news, social media, and other sources to gauge investor attitude.', icon: <SearchCheck className="h-8 w-8 mb-2 text-primary" /> },
  { name: 'Valuation Analysis', href: '/analysis/valuation', description: 'Estimate the economic worth of a business or asset.', icon: <ShoppingCart className="h-8 w-8 mb-2 text-primary" /> },
];

export default function AnalysisHubPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight">Data Analysis Tools</h1>
        <p className="text-muted-foreground mt-2">
          Choose an analysis type to evaluate market data, company financials, and investment opportunities.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        {analysisTypes.map((analysis) => (
          <Card key={analysis.name}>
            <CardHeader>
              <div className="flex items-center space-x-3">
                {analysis.icon}
                <CardTitle>{analysis.name}</CardTitle>
              </div>
              <CardDescription className="pt-2">{analysis.description}</CardDescription>
            </CardHeader>
            <CardFooter>
              <Button asChild variant="secondary" className="w-full">
                <Link href={analysis.href}>
                  Go to {analysis.name} <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
