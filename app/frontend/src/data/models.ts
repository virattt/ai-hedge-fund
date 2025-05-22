
export type ModelProvider = "Anthropic" | "DeepSeek" | "Gemini" | "Groq" | "OpenAI";
export interface ModelItem {
  display_name: string;
  model_name: string;
}

export type ModelItemWithProvider = ModelItem & { provider: ModelProvider };

const models: Record<ModelProvider, ModelItem[]> = {
  "Anthropic": [
    {
      "display_name": "claude-3.5-haiku",
      "model_name": "claude-3-5-haiku-latest"
    },
    {
      "display_name": "claude-3.7-sonnet",
      "model_name": "claude-3-7-sonnet-latest"
    }
  ],
  "DeepSeek": [
    {
      "display_name": "deepseek-r1",
      "model_name": "deepseek-reasoner"
    },
    {
      "display_name": "deepseek-v3",
      "model_name": "deepseek-chat"
    }
  ],
  "Gemini": [
    {
      "display_name": "gemini-2.0-flash",
      "model_name": "gemini-2.0-flash"
    },
    {
      "display_name": "gemini-2.5-pro",
      "model_name": "gemini-2.5-pro-exp-03-25"
    }
  ],
  "Groq": [
    {
      "display_name": "llama-4-scout-17b",
      "model_name": "meta-llama/llama-4-scout-17b-16e-instruct"
    },
    {
      "display_name": "llama-4-maverick-17b",
      "model_name": "meta-llama/llama-4-maverick-17b-128e-instruct"
    }
  ],
  "OpenAI": [
    {
      "display_name": "gpt-4.5",
      "model_name": "gpt-4.5-preview"
    },
    {
      "display_name": "gpt-4o",
      "model_name": "gpt-4o"
    },
    {
      "display_name": "o3",
      "model_name": "o3"
    },
    {
      "display_name": "o4-mini",
      "model_name": "o4-mini"
    }
  ]
} as const;

// Export the models with their respective providers
export const apiModels = Object.entries(models).reduce((acc, [provider, modelList]) => {
  const providerModels = modelList.map(model => ({
    ...model,
    provider: provider as ModelProvider
  }));
  return acc.concat(providerModels);
}, [] as ModelItemWithProvider[]);

// Find the GPT-4o model to use as default
export const defaultModel = apiModels.find(model => model.model_name === "gpt-4o") || null;