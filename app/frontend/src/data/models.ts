import { api } from '@/services/api';

export interface LanguageModel {
  display_name: string;
  model_name: string;
  provider: string;
}

// Cache for models to avoid repeated API calls
let languageModels: LanguageModel[] | null = null;

/**
 * Get the list of models from the backend API
 * Uses caching to avoid repeated API calls
 */
export const getModels = async (): Promise<LanguageModel[]> => {
  if (languageModels) {
    return languageModels;
  }

  try {
    languageModels = await api.getLanguageModels();
    return languageModels;
  } catch (error) {
    console.error('Failed to fetch models:', error);
    throw error; // Let the calling component handle the error
  }
};

// Map from model provider name to the API key provider name stored in the DB
const PROVIDER_TO_API_KEY: Record<string, string> = {
  OpenAI: 'OPENAI_API_KEY',
  Anthropic: 'ANTHROPIC_API_KEY',
  Groq: 'GROQ_API_KEY',
  DeepSeek: 'DEEPSEEK_API_KEY',
  Google: 'GOOGLE_API_KEY',
  xAI: 'XAI_API_KEY',
  OpenRouter: 'OPENROUTER_API_KEY',
  GigaChat: 'GIGACHAT_API_KEY',
  Alibaba: 'ALIBABA_API_KEY',
  Mistral: 'MISTRAL_API_KEY',
  Meta: 'META_API_KEY',
};

/**
 * Get the best default model based on configured API keys.
 * Priority: MLX (if MLX_BASE_URL set) > Ollama (if running) > Cloud (first provider with key set)
 */
export const getDefaultModel = async (): Promise<LanguageModel | null> => {
  try {
    const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const [models, apiKeysRaw] = await Promise.all([
      getModels(),
      fetch(`${API_BASE_URL}/api-keys`).then(r => r.ok ? r.json() : []).catch(() => []),
    ]);

    // Build a set of providers that have a key stored
    const configuredKeys = new Set<string>(
      (apiKeysRaw as Array<{ provider: string; has_key: boolean }>)
        .filter(k => k.has_key)
        .map(k => k.provider)
    );

    // 1. MLX — if MLX_BASE_URL is configured
    if (configuredKeys.has('MLX_BASE_URL')) {
      const mlx = models.find(m => m.provider === 'MLX');
      if (mlx) return mlx;
    }

    // 2. Ollama — if server is reachable
    try {
      const ollamaRes = await fetch(`${API_BASE_URL}/ollama/models`);
      if (ollamaRes.ok) {
        const ollamaData = await ollamaRes.json();
        if (Array.isArray(ollamaData.models) && ollamaData.models.length > 0) {
          const ollama = models.find(m => m.provider === 'Ollama');
          if (ollama) return ollama;
        }
      }
    } catch {
      // Ollama not available — continue
    }

    // 3. Cloud — first provider (in priority order) that has an API key stored
    const cloudOrder = ['Anthropic', 'OpenAI', 'Groq', 'Google', 'DeepSeek', 'xAI', 'OpenRouter', 'Alibaba', 'Mistral', 'Meta'];
    for (const provider of cloudOrder) {
      const keyName = PROVIDER_TO_API_KEY[provider];
      if (keyName && configuredKeys.has(keyName)) {
        const model = models.find(m => m.provider === provider);
        if (model) return model;
      }
    }

    return null;
  } catch (error) {
    console.error('Failed to get default model:', error);
    return null;
  }
};
