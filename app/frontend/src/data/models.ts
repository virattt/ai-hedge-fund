import { api } from '@/services/api';

export interface LanguageModel {
  display_name: string;
  model_name: string;
  provider: "Anthropic" | "DeepSeek" | "Google" | "Groq" | "OpenAI";
}

// Which providers have a key configured on the backend (from env vars only).
// API keys are never entered or stored in the UI.
export interface ModelStatus {
  configured_providers: string[];
  default_provider: string | null;
  default_model: { model_name: string; provider: string } | null;
}

// Cache for models to avoid repeated API calls
let languageModels: LanguageModel[] | null = null;

// Cache for backend model status (configured providers + default model)
let modelStatus: ModelStatus | null = null;

/**
 * Get which providers are configured on the backend, with caching.
 */
export const getModelStatus = async (): Promise<ModelStatus> => {
  if (modelStatus) {
    return modelStatus;
  }
  modelStatus = await api.getModelStatus();
  return modelStatus;
};

/**
 * Get the list of provider names that have an API key configured on the backend.
 * Returns an empty array on failure (callers treat that as "none configured").
 */
export const getConfiguredProviders = async (): Promise<string[]> => {
  try {
    const status = await getModelStatus();
    return status.configured_providers || [];
  } catch (error) {
    console.error('Failed to fetch configured providers:', error);
    return [];
  }
};

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

/**
 * Get the default model for the backend's configured provider.
 *
 * Mirrors the backend default so a per-agent node preselects a model whose provider
 * actually has a key (e.g. an Anthropic model on an Anthropic-only deploy) rather than
 * always defaulting to OpenAI's gpt-5.5. Falls back to gpt-5.5 / the first model if the
 * status endpoint is unavailable.
 */
export const getDefaultModel = async (): Promise<LanguageModel | null> => {
  try {
    const models = await getModels();
    try {
      const status = await getModelStatus();
      if (status.default_model) {
        const match = models.find(m => m.model_name === status.default_model!.model_name);
        if (match) {
          return match;
        }
      }
      // A provider is configured but its default model isn't in the list, or nothing is
      // configured: prefer a model whose provider has a key, else fall through.
      const configured = new Set(status.configured_providers || []);
      const enabled = models.find(m => configured.has(m.provider));
      if (enabled) {
        return enabled;
      }
    } catch {
      // Status unavailable — fall back to the static default below.
    }
    return models.find(model => model.model_name === "gpt-5.5") || models[0] || null;
  } catch (error) {
    console.error('Failed to get default model:', error);
    return null;
  }
};
