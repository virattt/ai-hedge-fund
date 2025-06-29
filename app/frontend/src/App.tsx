import { useState } from 'react';
import { Layout } from './components/Layout';
import { EnhancedLayout } from './components/enhanced-layout';
import { Toaster } from './components/ui/sonner';
import { Badge } from './components/ui/badge';
import { ToggleGroup, ToggleGroupItem } from './components/ui/toggle-group';
import { 
  Workflow, 
  BarChart3
} from 'lucide-react';

export default function App() {
  const [currentMode, setCurrentMode] = useState<'enhanced' | 'workflow'>('enhanced');

  return (
    <>
      {/* Mode Selection Header */}
      <div className="border-b bg-white">
        <div className="px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <h1 className="text-lg font-bold">AI Hedge Fund Platform</h1>
              <Badge variant="outline">v2.0</Badge>
            </div>
            
            <div className="flex items-center space-x-4">
              <ToggleGroup
                type="single"
                value={currentMode}
                onValueChange={(value: string) => value && setCurrentMode(value as 'enhanced' | 'workflow')}
                className="bg-gray-100 p-1 rounded-lg"
              >
                <ToggleGroupItem value="enhanced" className="flex items-center space-x-2">
                  <BarChart3 className="h-4 w-4" />
                  <span>Trading Dashboard</span>
                </ToggleGroupItem>
                <ToggleGroupItem value="workflow" className="flex items-center space-x-2">
                  <Workflow className="h-4 w-4" />
                  <span>Workflow Builder</span>
                </ToggleGroupItem>
              </ToggleGroup>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      {currentMode === 'enhanced' ? <EnhancedLayout /> : <Layout />}
      
      <Toaster />
    </>
  );
}
