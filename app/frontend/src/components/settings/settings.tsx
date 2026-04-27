import { cn } from '@/lib/utils';
import { CubeIcon } from '@radix-ui/react-icons';
import { Key, Palette } from 'lucide-react';
import { useState } from 'react';
import { ApiKeysSettings, Models } from './';
import { ThemeSettings } from './appearance';

interface SettingsProps {
  className?: string;
}

interface SettingsNavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description?: string;
}

export function Settings({ className }: SettingsProps) {
  const [selectedSection, setSelectedSection] = useState('api');

  const navigationItems: SettingsNavItem[] = [
    {
      id: 'api',
      label: 'API Keys',
      icon: Key,
      description: 'API endpoints and authentication',
    },
    {
      id: 'models',
      label: 'Models',
      icon: CubeIcon,
      description: 'Local and cloud AI models',
    },
    {
      id: 'theme',
      label: 'Theme',
      icon: Palette,
      description: 'Theme and display preferences',
    },
  ];

  const renderContent = () => {
    switch (selectedSection) {
      case 'models':
        return <Models />;
      case 'theme':
        return <ThemeSettings />;
      case 'api':
        return <ApiKeysSettings />;
      default:
        return <Models />;
    }
  };

  return (
    <div className={cn("flex justify-center h-full overflow-hidden bg-panel", className)}>
      <div className="flex w-full max-w-7xl mx-auto">
        {/* Left Navigation Pane */}
        <div className="w-60 bg-panel flex-shrink-0">
          <div className="p-4 border-b">
            <h1 className="text-lg font-semibold text-primary">Settings</h1>
          </div>
          <nav className="p-2">
            {navigationItems.map((item) => {
              const Icon = item.icon;
              const isSelected = selectedSection === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setSelectedSection(item.id)}
                  className={cn(
                    "w-full flex items-center gap-3 px-3 py-2 text-left rounded-md text-sm transition-colors",
                    isSelected 
                      ? "active-bg text-blue-500" 
                      : "text-primary hover-item"
                  )}
                >
                  <Icon className="h-4 w-4 flex-shrink-0" />
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Right Content Pane */}
        <div className="flex-1 overflow-auto bg-panel">
          <div className="p-8 max-w-4xl">
            {renderContent()}
          </div>
        </div>
      </div>
    </div>
  );
} 