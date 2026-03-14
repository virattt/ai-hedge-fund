import { Button } from '@/components/ui/button';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Brain, Newspaper, Workflow } from 'lucide-react';
import { Link } from 'react-router-dom';

const features = [
  {
    icon: Brain,
    title: '17+ AI Analysts',
    description:
      'Multiple AI analyst agents analyze stocks in parallel — from fundamentals and technicals to sentiment and insider trading.',
  },
  {
    icon: Workflow,
    title: 'Visual Flow Editor',
    description:
      'Build and customize your analysis pipeline with a drag-and-drop flow editor. Connect agents, configure risk management, and run analysis.',
  },
  {
    icon: Newspaper,
    title: 'News Scraping & Analysis',
    description:
      'Scrape financial news and earnings reports from the web, then feed them into your AI analysts for real-time insight.',
  },
];

export function HomePage() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center p-8 overflow-auto">
      <div className="max-w-3xl w-full space-y-10">
        {/* Hero */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold tracking-tight text-foreground">
            AI Hedge Fund
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            An AI-powered hedge fund proof of concept. Multiple AI analyst agents analyze stocks in parallel, feed signals to a risk manager, then a portfolio manager makes final trading decisions.
          </p>
          <Button asChild size="lg" className="mt-4">
            <Link to="/editor">Open Editor &rarr;</Link>
          </Button>
        </div>

        {/* Feature cards */}
        <div className="grid gap-4 sm:grid-cols-3">
          {features.map(({ icon: Icon, title, description }) => (
            <Card key={title}>
              <CardHeader>
                <Icon className="h-8 w-8 text-muted-foreground mb-2" />
                <CardTitle className="text-base">{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
