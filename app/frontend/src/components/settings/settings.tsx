import { cn } from '@/lib/utils';
import { CubeIcon } from '@radix-ui/react-icons';
import { Key, Palette, Settings2, Workflow } from 'lucide-react';
import { useState } from 'react';
import { ApiKeysSettings, AppearanceSettings, FlowsSettings, GeneralSettings, Models } from './';

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
  const [selectedSection, setSelectedSection] = useState('models');

  const navigationItems: SettingsNavItem[] = [
    {
      id: 'general',
      label: 'General',
      icon: Settings2,
      description: 'General application settings and preferences',
    },
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
      id: 'flows',
      label: 'Flows',
      icon: Workflow,
      description: 'Flow and node configuration',
    },
    {
      id: 'appearance',
      label: 'Appearance',
      icon: Palette,
      description: 'Theme and display preferences',
    },
  ];

  const renderContent = () => {
    switch (selectedSection) {
      case 'general':
        return <GeneralSettings />;
      case 'models':
        return <Models />;
      case 'flows':
        return <FlowsSettings />;
      case 'appearance':
        return <AppearanceSettings />;
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
          <div className="p-4 border-b border-gray-700 dark:border-gray-800">
            <h1 className="text-lg font-semibold text-gray-100 dark:text-gray-100">Settings</h1>
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
                      ? "bg-gray-700 dark:bg-gray-800 text-gray-100 dark:text-gray-100 shadow-sm" 
                      : "text-gray-300 dark:text-gray-400 hover:text-gray-100 dark:hover:text-gray-100 hover:bg-gray-700/50 dark:hover:bg-gray-800/50"
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