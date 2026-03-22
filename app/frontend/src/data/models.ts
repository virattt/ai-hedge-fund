import { api } from '@/services/api';

export interface LanguageModel {
  display_name: string;
  model_name: string;
  provider: "Anthropic" | "DeepSeek" | "Google" | "Groq" | "OpenAI";
}

// Resolved cache and in-flight promise — prevents duplicate API calls
// when multiple nodes mount at the same time.
let languageModels: LanguageModel[] | null = null;
let pendingFetch: Promise<LanguageModel[]> | null = null;

/**
 * Get the list of models from the backend API.
 * Multiple concurrent callers share a single in-flight request.
 */
export const getModels = async (): Promise<LanguageModel[]> => {
  if (languageModels) {
    return languageModels;
  }

  if (pendingFetch) {
    return pendingFetch;
  }

  pendingFetch = api.getLanguageModels().then((models) => {
    languageModels = models;
    pendingFetch = null;
    return models;
  }).catch((error) => {
    pendingFetch = null;
    console.error('Failed to fetch models:', error);
    throw error;
  });

  return pendingFetch;
};

/**
 * Get the default model (GPT-4.1) from the models list
 */
export const getDefaultModel = async (): Promise<LanguageModel | null> => {
  try {
    const models = await getModels();
    return models.find(model => model.model_name === "gpt-4.1") || models[0] || null;
  } catch (error) {
    console.error('Failed to get default model:', error);
    return null;
  }
};
