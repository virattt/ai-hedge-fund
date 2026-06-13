import { Badge } from '@/components/ui/badge';
import { useI18n } from '@/i18n/use-i18n';
import { cn } from '@/lib/utils';
import { Cloud, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';

interface CloudModelsProps {
  className?: string;
}

interface CloudModel {
  display_name: string;
  model_name: string;
  provider: string;
}

interface ModelProvider {
  name: string;
  models: Array<{
    display_name: string;
    model_name: string;
  }>;
}

export function CloudModels({ className }: CloudModelsProps) {
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useI18n();

  const fetchProviders = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/language-models/providers');
      if (response.ok) {
        const data = await response.json();
        setProviders(data.providers);
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`Failed to fetch providers: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Failed to fetch cloud model providers:', error);
      setError(t('ollama.backendConnectionError'));
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  // Flatten all models from all providers into a single array
  const allModels: CloudModel[] = providers.flatMap(provider =>
    provider.models.map(model => ({
      ...model,
      provider: provider.name
    }))
  ).sort((a, b) => a.provider.localeCompare(b.provider));

  return (
    <div className={cn("space-y-6", className)}>

      {error && (
        <div className="bg-red-900/20 border border-red-600/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Cloud className="h-5 w-5 text-red-500 mt-0.5" />
            <div>
              <h4 className="font-medium text-red-300">{t('ollama.errorTitle')}</h4>
              <p className="text-sm text-red-500 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-primary
          ">{t('models.availableModels')}</h3>
          <span className="text-xs text-muted-foreground">
            {t('models.countSummary', { modelCount: allModels.length, providerCount: providers.length })}
          </span>
        </div>

        {loading ? (
          <div className="text-center py-8">
            <RefreshCw className="h-8 w-8 mx-auto mb-2 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{t('models.loadingCloud')}</p>
          </div>
        ) : allModels.length > 0 ? (
          <div className="space-y-1">
            {allModels.map((model) => (
              <div
                key={`${model.provider}-${model.model_name}`}
                className="group flex items-center justify-between bg-muted hover-bg rounded-md px-3 py-2.5 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate text-primary">{model.display_name}</span>
                    {model.model_name !== model.display_name && (
                      <span className="font-mono text-xs text-muted-foreground">
                        {model.model_name}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge className="text-xs text-primary bg-primary/10 border-primary/30 hover:bg-primary/20 hover:border-primary/50">
                    {model.provider}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        ) : (
          !loading && (
            <div className="text-center py-8 text-muted-foreground">
              <Cloud className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">{t('models.noneAvailable')}</p>
            </div>
          )
        )}
      </div>
    </div>
  );
}
