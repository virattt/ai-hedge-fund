import { Badge } from '@/components/ui/badge';
import { cn, getProviderColor } from '@/lib/utils';
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
      setError('Failed to connect to backend service');
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
            <Cloud className="h-5 w-5 text-red-400 mt-0.5" />
            <div>
              <h4 className="font-medium text-red-300">Error</h4>
              <p className="text-sm text-red-400 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-gray-100">Available Models</h3>
          <span className="text-xs text-gray-400">
            {allModels.length} models from {providers.length} providers
          </span>
        </div>

        {loading ? (
          <div className="text-center py-8">
            <RefreshCw className="h-8 w-8 mx-auto mb-2 animate-spin text-gray-400" />
            <p className="text-sm text-gray-400">Loading cloud models...</p>
          </div>
        ) : allModels.length > 0 ? (
          <div className="space-y-1">
            {allModels.map((model) => (
              <div 
                key={`${model.provider}-${model.model_name}`}
                className="group flex items-center justify-between bg-gray-700/30 hover:bg-gray-700/50 rounded-md px-3 py-2.5 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate text-gray-200">{model.display_name}</span>
                    {model.model_name !== model.display_name && (
                      <span className="font-mono text-xs text-gray-400">
                        {model.model_name}
                      </span>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Badge className={cn("text-xs", getProviderColor(model.provider))}>
                    {model.provider}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        ) : (
          !loading && (
            <div className="text-center py-8 text-gray-400">
              <Cloud className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No models available</p>
            </div>
          )
        )}
      </div>
    </div>
  );
} 