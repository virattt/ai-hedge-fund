import { useState } from 'react';
import { Flow } from './components/Flow';
import { Layout } from './components/Layout';
import { Portfolio } from './components/Portfolio';
import { Button } from './components/ui/button';
import { PieChart, TrendingUp } from 'lucide-react';

type ViewType = 'flow' | 'portfolio';

export default function App() {
  const [currentView, setCurrentView] = useState<ViewType>('portfolio');
  const [showLeftSidebar, setShowLeftSidebar] = useState(true);

  const navigationItems = [
    { id: 'flow', label: 'Agent Flow', icon: TrendingUp },
    { id: 'portfolio', label: 'Portfolio', icon: PieChart },
  ] as const;

  console.log(showLeftSidebar);

  const leftSidebar = showLeftSidebar ? (
    <div className="p-4 bg-gray-900 text-white h-full min-w-[240px]">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-blue-400">AI Hedge Fund</h2>
        <p className="text-sm text-gray-400">Trading Intelligence</p>
      </div>
      
      <nav className="space-y-2">
        {navigationItems.map((item) => {
          const Icon = item.icon;
          return (
            <Button
              key={item.id}
              variant={currentView === item.id ? "default" : "ghost"}
              className={`w-full justify-start gap-3 ${
                currentView === item.id 
                  ? 'bg-blue-600 text-white hover:bg-blue-700' 
                  : 'text-gray-300 hover:text-white hover:bg-gray-800'
              }`}
              onClick={() => setCurrentView(item.id as ViewType)}
            >
              <Icon size={18} />
              {item.label}
            </Button>
          );
        })}
      </nav>
      
      <div className="absolute bottom-4 left-4 right-4">
        <Button
          variant="ghost"
          size="sm"
          className="w-20 text-gray-400 hover:text-white"
          onClick={() => setShowLeftSidebar(false)}
        >
          Collapse
        </Button>
      </div>
    </div>
  ) : (
    <div className="p-2 bg-gray-900">
      <Button
        variant="ghost"
        size="sm"
        className="text-gray-400 hover:text-white"
        onClick={() => setShowLeftSidebar(true)}
      >
        →
      </Button>
    </div>
  );

  const renderCurrentView = () => {
    console.log(currentView);
    switch (currentView) {
      case 'flow':
        return <Flow />;
      case 'portfolio':
        return <Portfolio />;
      default:
        return <Portfolio />;
    }
  };

  return (
    <Layout leftSidebar={leftSidebar} currentView={currentView}>
      {renderCurrentView()}
    </Layout>
  );
}
