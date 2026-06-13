import { cn } from '@/lib/utils';
import { Cloud, Server } from 'lucide-react';
import { useState } from 'react';
import { CloudModels } from './models/cloud';
import { OllamaSettings } from './models/ollama';
import { useI18n } from '@/i18n/use-i18n';

interface ModelsProps {
  className?: string;
}

interface ModelSection {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  component: React.ComponentType;
}

export function Models({ className }: ModelsProps) {
  const [selectedSection, setSelectedSection] = useState('cloud');
  const { t } = useI18n();

  const modelSections: ModelSection[] = [
    {
      id: 'cloud',
      label: t('models.cloud'),
      icon: Cloud,
      description: t('models.cloudDescription'),
      component: CloudModels,
    },
    {
      id: 'local',
      label: t('models.local'),
      icon: Server,
      description: t('models.localDescription'),
      component: OllamaSettings,
    },
  ];

  const renderContent = () => {
    const section = modelSections.find(s => s.id === selectedSection);
    if (!section) return null;

    const Component = section.component;
    return <Component />;
  };

  return (
    <div className={cn("space-y-6", className)}>
      <div>
        <h2 className="text-xl font-semibold text-primary mb-2">{t('models.title')}</h2>
        <p className="text-sm text-muted-foreground">
          {t('models.description')}
        </p>
      </div>

      {/* Model Type Navigation */}
      <div className="flex space-x-1 bg-muted p-1 rounded-lg">
        {modelSections.map((section) => {
          const Icon = section.icon;
          const isSelected = selectedSection === section.id;
          const isDisabled = false; // Enable all tabs now that cloud models is functional

          return (
            <button
              key={section.id}
              onClick={() => !isDisabled && setSelectedSection(section.id)}
              disabled={isDisabled}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-colors",
                isSelected
                  ? "active-bg text-blue-500 shadow-sm"
                  : isDisabled
                  ? "text-muted-foreground cursor-not-allowed"
                  : "text-primary hover:text-primary hover-bg"
              )}
            >
              <Icon className="h-4 w-4" />
              {section.label}
              {isDisabled && (
                <span className="text-xs bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                  {t('models.soon')}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content Area */}
      <div className="mt-6">
        {renderContent()}
      </div>
    </div>
  );
}
