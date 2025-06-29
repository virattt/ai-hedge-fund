import React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from '@/components/ui/navigation-menu';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  BarChart3,
  TrendingUp,
  Globe,
  MessageSquare,
  Settings,
  Target,
  Activity,
  PieChart,
  Briefcase,
  DollarSign,
  AlertTriangle,
  LineChart,
  Map,
  Users,
  Zap,
  Database,
} from 'lucide-react';

interface MainNavProps {
  currentView: string;
  onViewChange: (view: string) => void;
  className?: string;
}

const navigationItems = [
  {
    title: 'Portfolio',
    href: 'portfolio',
    icon: Briefcase,
    description: 'Portfolio overview and performance',
    items: [
      {
        title: 'Dashboard',
        href: 'portfolio-dashboard',
        icon: PieChart,
        description: 'Real-time portfolio analysis and metrics',
      },
      {
        title: 'Holdings',
        href: 'portfolio-holdings',
        icon: DollarSign,
        description: 'Current positions and allocations',
      },
      {
        title: 'Performance',
        href: 'portfolio-performance',
        icon: TrendingUp,
        description: 'Historical performance and returns',
      },
      {
        title: 'Risk Analysis',
        href: 'portfolio-risk',
        icon: AlertTriangle,
        description: 'Risk metrics and exposure analysis',
      },
    ],
  },
  {
    title: 'Trading Universe',
    href: 'universe',
    icon: Target,
    description: 'Investment universe selection and management',
    items: [
      {
        title: 'Universe Selection',
        href: 'universe-selection',
        icon: Target,
        description: 'Choose your trading universe and criteria',
      },
      {
        title: 'Screener',
        href: 'universe-screener',
        icon: Database,
        description: 'Screen securities by fundamental criteria',
      },
      {
        title: 'Sector Analysis',
        href: 'universe-sectors',
        icon: Map,
        description: 'Sector allocation and rotation analysis',
      },
    ],
  },
  {
    title: 'Market Intelligence',
    href: 'intelligence',
    icon: Activity,
    description: 'Real-time market analysis and insights',
    items: [
      {
        title: 'Economic Indicators',
        href: 'economic-indicators',
        icon: BarChart3,
        description: 'Fed policy, GDP, inflation, and employment data',
      },
      {
        title: 'Political Signals',
        href: 'political-signals',
        icon: Globe,
        description: 'Political events and policy impact analysis',
      },
      {
        title: 'Sentiment Analysis',
        href: 'sentiment-analysis',
        icon: MessageSquare,
        description: 'Social media and news sentiment tracking',
      },
      {
        title: 'Market Overview',
        href: 'market-overview',
        icon: LineChart,
        description: 'Comprehensive market regime analysis',
      },
    ],
  },
  {
    title: 'AI Agents',
    href: 'agents',
    icon: Users,
    description: 'AI analyst configuration and insights',
    items: [
      {
        title: 'Agent Performance',
        href: 'agent-performance',
        icon: TrendingUp,
        description: 'Track AI agent accuracy and performance',
      },
      {
        title: 'Agent Configuration',
        href: 'agent-config',
        icon: Settings,
        description: 'Configure and customize AI analysts',
      },
      {
        title: 'Decision Flow',
        href: 'decision-flow',
        icon: Zap,
        description: 'Visual workflow builder for trading logic',
      },
    ],
  },
];

export function MainNav({ currentView, onViewChange, className }: MainNavProps) {
  const handleItemClick = (href: string) => {
    onViewChange(href);
  };

  const getCurrentSection = () => {
    return navigationItems.find(item => 
      item.href === currentView || 
      item.items?.some(subItem => subItem.href === currentView)
    )?.title || 'Portfolio';
  };

  return (
    <div className={cn('flex items-center space-x-2', className)}>
      {/* Main Navigation Menu */}
      <NavigationMenu>
        <NavigationMenuList>
          {navigationItems.map((item) => (
            <NavigationMenuItem key={item.href}>
              <NavigationMenuTrigger className="flex items-center space-x-2">
                <item.icon className="h-4 w-4" />
                <span>{item.title}</span>
                {item.title === 'Market Intelligence' && (
                  <Badge variant="secondary" className="ml-2 text-xs">
                    Live
                  </Badge>
                )}
              </NavigationMenuTrigger>
              <NavigationMenuContent>
                <div className="grid w-[600px] grid-cols-2 gap-3 p-4">
                  <div className="row-span-3">
                    <NavigationMenuLink asChild>
                      <button
                        onClick={() => handleItemClick(item.href)}
                        className="flex h-full w-full select-none flex-col justify-end rounded-md bg-gradient-to-b from-muted/50 to-muted p-6 no-underline outline-none focus:shadow-md hover:bg-muted/80 transition-colors text-left"
                      >
                        <item.icon className="h-6 w-6 mb-2" />
                        <div className="mb-2 mt-4 text-lg font-medium">
                          {item.title}
                        </div>
                        <p className="text-sm leading-tight text-muted-foreground">
                          {item.description}
                        </p>
                      </button>
                    </NavigationMenuLink>
                  </div>
                  <div className="space-y-1">
                    {item.items?.map((subItem) => (
                      <NavigationMenuLink key={subItem.href} asChild>
                        <button
                          onClick={() => handleItemClick(subItem.href)}
                          className="block select-none space-y-1 rounded-md p-3 leading-none no-underline outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground w-full text-left"
                        >
                          <div className="flex items-center space-x-2">
                            <subItem.icon className="h-4 w-4" />
                            <div className="text-sm font-medium leading-none">
                              {subItem.title}
                            </div>
                          </div>
                          <p className="line-clamp-2 text-sm leading-snug text-muted-foreground">
                            {subItem.description}
                          </p>
                        </button>
                      </NavigationMenuLink>
                    ))}
                  </div>
                </div>
              </NavigationMenuContent>
            </NavigationMenuItem>
          ))}
        </NavigationMenuList>
      </NavigationMenu>

      {/* Quick Actions */}
      <div className="flex items-center space-x-2 ml-4">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="flex items-center space-x-2">
              <Zap className="h-4 w-4" />
              <span>Quick Actions</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>Quick Actions</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => handleItemClick('portfolio-analysis')}>
              <BarChart3 className="mr-2 h-4 w-4" />
              Run Portfolio Analysis
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleItemClick('market-scan')}>
              <Activity className="mr-2 h-4 w-4" />
              Market Scan
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleItemClick('risk-check')}>
              <AlertTriangle className="mr-2 h-4 w-4" />
              Risk Check
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => handleItemClick('settings')}>
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Current View Indicator */}
        <Badge variant="outline" className="flex items-center space-x-1">
          <span className="w-2 h-2 bg-green-500 rounded-full"></span>
          <span>{getCurrentSection()}</span>
        </Badge>
      </div>
    </div>
  );
}