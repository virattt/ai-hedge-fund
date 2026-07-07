import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getModelStatus, type ModelStatus } from '@/data/models';
import { cn } from '@/lib/utils';
import { AlertTriangle, CheckCircle2, ExternalLink, Key } from 'lucide-react';
import { useEffect, useState } from 'react';

interface ProviderInfo {
  // Matches the backend ModelProvider value reported in configured_providers.
  provider: string;
  label: string;
  description: string;
  url: string;
  // The environment variable(s) that supply this provider's key.
  envVars: string[];
}

// Providers the model registry can use. Configured state comes from the backend.
const LLM_PROVIDERS: ProviderInfo[] = [
  { provider: 'OpenAI', label: 'OpenAI', description: 'GPT models (e.g. gpt-5.5)', url: 'https://platform.openai.com/', envVars: ['OPENAI_API_KEY'] },
  { provider: 'Anthropic', label: 'Anthropic', description: 'Claude models (e.g. claude-opus-4-8)', url: 'https://console.anthropic.com/', envVars: ['ANTHROPIC_API_KEY'] },
  { provider: 'Google', label: 'Google', description: 'Gemini models', url: 'https://ai.dev/', envVars: ['GOOGLE_API_KEY'] },
  { provider: 'DeepSeek', label: 'DeepSeek', description: 'DeepSeek models', url: 'https://deepseek.com/', envVars: ['DEEPSEEK_API_KEY'] },
  { provider: 'xAI', label: 'xAI', description: 'Grok models', url: 'https://x.ai/', envVars: ['XAI_API_KEY'] },
  { provider: 'Kimi', label: 'Moonshot (Kimi)', description: 'Kimi / Moonshot models', url: 'https://platform.moonshot.ai/', envVars: ['MOONSHOT_API_KEY'] },
  { provider: 'Groq', label: 'Groq', description: 'Groq-hosted models', url: 'https://groq.com/', envVars: ['GROQ_API_KEY'] },
  { provider: 'OpenRouter', label: 'OpenRouter', description: 'OpenRouter models', url: 'https://openrouter.ai/', envVars: ['OPENROUTER_API_KEY'] },
];

export function ApiKeysSettings() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getModelStatus()
      .then((s) => {
        if (!cancelled) {
          setStatus(s);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e?.message || 'Failed to load model status');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const configured = new Set(status?.configured_providers || []);
  // Ollama needs no key, so ignore it when deciding whether an LLM key is set.
  const llmConfigured = LLM_PROVIDERS.filter((p) => configured.has(p.provider));
  const noneConfigured = !loading && !error && llmConfigured.length === 0;

  return (
    <div className="max-w-3xl">
      <div className="mb-6 flex items-center gap-2">
        <Key className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold text-primary">API Keys</h2>
      </div>

      {/* Env-var-only posture */}
      <Card className="mb-4 border-border bg-node">
        <CardContent className="pt-4 text-sm text-muted-foreground">
          API keys are read <span className="font-medium text-primary">only from backend environment variables</span> — they
          are never entered or stored in this UI. Set them on your backend service (for a Render deploy, in the service's
          Environment settings), then redeploy. The simplest setup is a single{' '}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">LLM_API_KEY</code> plus{' '}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">LLM_PROVIDER</code> (e.g.{' '}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">Anthropic</code>). Provider-specific vars like{' '}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">OPENAI_API_KEY</code> also work.
        </CardContent>
      </Card>

      {loading && <div className="text-sm text-muted-foreground">Checking configured providers…</div>}

      {error && (
        <Card className="mb-4 border-red-500/40 bg-red-500/5">
          <CardContent className="flex items-center gap-2 pt-4 text-sm text-red-500">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Couldn't reach the backend to check configured providers: {error}
          </CardContent>
        </Card>
      )}

      {noneConfigured && (
        <Card className="mb-4 border-amber-500/50 bg-amber-500/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" />
              No LLM API key configured
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-amber-700 dark:text-amber-300">
            The app can't run until an LLM key is set on the backend. Add{' '}
            <code className="rounded bg-black/10 px-1 py-0.5 text-xs dark:bg-white/10">LLM_API_KEY</code> and{' '}
            <code className="rounded bg-black/10 px-1 py-0.5 text-xs dark:bg-white/10">LLM_PROVIDER</code> (or a
            provider-specific key like{' '}
            <code className="rounded bg-black/10 px-1 py-0.5 text-xs dark:bg-white/10">OPENAI_API_KEY</code>) as
            environment variables on your backend service, then redeploy.
          </CardContent>
        </Card>
      )}

      {!loading && !error && !noneConfigured && (
        <div className="mb-4 flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
          <CheckCircle2 className="h-4 w-4" />
          Configured: {llmConfigured.map((p) => p.label).join(', ')}
          {status?.default_model && (
            <span className="text-muted-foreground">
              · default model <code className="rounded bg-muted px-1 py-0.5 text-xs">{status.default_model.model_name}</code>
            </span>
          )}
        </div>
      )}

      {/* Provider list */}
      <div className="flex flex-col gap-2">
        {LLM_PROVIDERS.map((p) => {
          const isConfigured = configured.has(p.provider);
          return (
            <div
              key={p.provider}
              className="flex items-center justify-between rounded-md border border-border bg-node px-3 py-2"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    {p.label}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  <code className="rounded bg-muted px-1 py-0.5 text-xs text-muted-foreground">{p.envVars.join(' / ')}</code>
                </div>
                <div className="text-xs text-muted-foreground">{p.description}</div>
              </div>
              <span
                className={cn(
                  'shrink-0 rounded-full px-2 py-0.5 text-xs font-medium',
                  isConfigured
                    ? 'bg-green-500/15 text-green-600 dark:text-green-400'
                    : 'bg-muted text-muted-foreground'
                )}
              >
                {isConfigured ? 'Configured' : 'Not configured'}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-6 text-xs text-muted-foreground">
        Market data uses <code className="rounded bg-muted px-1 py-0.5">FINANCIAL_DATASETS_API_KEY</code> (also an
        environment variable). Free tickers (AAPL, GOOGL, MSFT, NVDA, TSLA) work without it.
      </div>
    </div>
  );
}
