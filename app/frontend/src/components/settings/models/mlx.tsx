import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Brain, CheckCircle, Cpu, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';

interface MlxModel {
  display_name: string;
  model_name: string;
  provider: string;
}

interface MlxStatus {
  running: boolean;
  server_url: string;
  error?: string;
}

export function MlxSettings() {
  const [models, setModels] = useState<MlxModel[]>([]);
  const [status, setStatus] = useState<MlxStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMlxStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/mlx/status');
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
        setError(null);
      } else {
        setStatus({ running: false, server_url: '' });
      }
    } catch {
      setStatus({ running: false, server_url: '' });
    }
  };

  const fetchMlxModels = async () => {
    try {
      const response = await fetch('http://localhost:8000/language-models/');
      if (response.ok) {
        const data = await response.json();
        const mlxModels = (data.models || []).filter((m: MlxModel) => m.provider === 'MLX' && m.model_name !== '-');
        setModels(mlxModels);
      }
    } catch (err) {
      console.error('Failed to fetch MLX models:', err);
    }
  };

  const refresh = async () => {
    setLoading(true);
    setError(null);
    await Promise.all([fetchMlxStatus(), fetchMlxModels()]);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-primary mb-2">MLX Local Models</h3>
          <p className="text-sm text-muted-foreground">
            Run AI models locally on Apple Silicon using{' '}
            <button
              className="underline hover:no-underline text-muted-foreground"
              onClick={() => window.open('https://github.com/ml-explore/mlx-examples/tree/main/llms', '_blank')}
            >
              mlx-lm
            </button>.
            Set the server URL in API Keys → MLX Local Models.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="flex items-center gap-1">
            {status === null ? (
              <RefreshCw className="h-3 w-3 animate-spin" />
            ) : status.running ? (
              <CheckCircle className="h-3 w-3" />
            ) : (
              <AlertTriangle className="h-3 w-3" />
            )}
            {status === null ? 'Checking...' : status.running ? 'Running' : 'Not Running'}
          </Badge>
          <Button
            size="sm"
            onClick={refresh}
            disabled={loading}
            className="text-primary hover:bg-primary/20 hover:text-primary bg-primary/10 border-primary/30 hover:border-primary/50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-600/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-red-400 mt-0.5" />
            <div>
              <h4 className="font-medium text-red-300">Error</h4>
              <p className="text-sm text-red-400 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {status && !status.running && (
        <div className="bg-muted rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Cpu className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div>
              <h4 className="font-medium text-muted-foreground">MLX Server Not Running</h4>
              <p className="text-sm text-muted-foreground mt-1">
                Start your MLX LM server with:{' '}
                <code className="bg-muted-foreground/20 px-1.5 py-0.5 rounded text-xs font-mono">
                  mlx_lm.server --model &lt;model-id&gt;
                </code>
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Configure the server URL in <strong>API Keys → MLX Local Models</strong>.
              </p>
            </div>
          </div>
        </div>
      )}

      {status?.running && (
        <div className="flex items-center gap-2 bg-muted rounded-lg p-4">
          <CheckCircle className="h-5 w-5 text-primary" />
          <div>
            <span className="font-medium text-primary">MLX Server Running</span>
            <p className="text-sm text-muted-foreground">Available at {status.server_url}</p>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-primary">Available Models</h3>
          <span className="text-xs text-muted-foreground">{models.length} models</span>
        </div>

        {models.length > 0 ? (
          <div className="space-y-1">
            {models.map((model) => (
              <div
                key={model.model_name}
                className="flex items-center justify-between bg-muted hover-bg rounded-md px-3 py-2.5 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-primary">{model.display_name}</span>
                    <span className="font-mono text-xs text-muted-foreground truncate">{model.model_name}</span>
                  </div>
                </div>
                <Badge className="text-xs text-primary bg-primary/10 border-primary/30 ml-2 flex-shrink-0">
                  MLX
                </Badge>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <Brain className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No MLX models loaded</p>
          </div>
        )}
      </div>

      <div className="bg-muted/50 rounded-lg p-4 space-y-2">
        <h4 className="text-sm font-medium text-primary">Quick Start</h4>
        <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">
          <li>Install: <code className="bg-muted px-1 rounded font-mono">pip install mlx-lm</code></li>
          <li>Start server: <code className="bg-muted px-1 rounded font-mono">mlx_lm.server --model mlx-community/Llama-3.1-8B-Instruct-4bit</code></li>
          <li>In agent nodes, select any MLX model from the model dropdown</li>
          <li>Optionally set a custom server URL in <strong>API Keys → MLX Local Models</strong></li>
        </ol>
      </div>
    </div>
  );
}
