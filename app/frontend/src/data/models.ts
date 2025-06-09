import { ModelProvider } from '@/services/types';

export interface ModelItem {
  display_name: string;
  model_name: string;
  provider: "Anthropic" | "DeepSeek" | "Gemini" | "Groq" | "OpenAI";
}

// Helper function to map frontend provider strings to backend ModelProvider enum
export function mapProviderToEnum(provider: string): ModelProvider | undefined {
  switch (provider.toLowerCase()) {
    case 'openai':
      return ModelProvider.OPENAI;
    case 'anthropic':
      return ModelProvider.ANTHROPIC;
    case 'google':
    case 'gemini':
      return ModelProvider.GOOGLE;
    case 'azure':
      return ModelProvider.AZURE;
    case 'deepseek':
      return ModelProvider.DEEPSEEK;
    case 'groq':
      return ModelProvider.GROQ;
    default:
      return undefined;
  }
}

export const apiModels: ModelItem[] = [
  {
    "display_name": "Claude Haiku 3.5",
    "model_name": "claude-3-5-haiku-latest",
    "provider": "Anthropic"
  },
  {
    "display_name": "Claude Sonnet 4",
    "model_name": "claude-sonnet-4-20250514",
    "provider": "Anthropic"
  },
  {
    "display_name": "Claude Opus 4",
    "model_name": "claude-opus-4-20250514",
    "provider": "Anthropic"
  },
  {
    "display_name": "DeepSeek R1",
    "model_name": "deepseek-reasoner",
    "provider": "DeepSeek"
  },
  {
    "display_name": "DeepSeek V3",
    "model_name": "deepseek-chat",
    "provider": "DeepSeek"
  },
  {
    "display_name": "Gemini 2.5 Flash",
    "model_name": "gemini-2.5-flash-preview-05-20",
    "provider": "Gemini"
  },
  {
    "display_name": "Gemini 2.5 Pro",
    "model_name": "gemini-2.5-pro-preview-06-05",
    "provider": "Gemini"
  },
  {
    "display_name": "Llama 4 Scout (17b)",
    "model_name": "meta-llama/llama-4-scout-17b-16e-instruct",
    "provider": "Groq"
  },
  {
    "display_name": "Llama 4 Maverick (17b)",
    "model_name": "meta-llama/llama-4-maverick-17b-128e-instruct",
    "provider": "Groq"
  },
  {
    "display_name": "GPT 4o",
    "model_name": "gpt-4o",
    "provider": "OpenAI"
  },
  {
    "display_name": "GPT 4.1",
    "model_name": "gpt-4.1-2025-04-14",
    "provider": "OpenAI"
  },
  {
    "display_name": "GPT 4.5",
    "model_name": "gpt-4.5-preview",
    "provider": "OpenAI"
  },
  {
    "display_name": "o3",
    "model_name": "o3",
    "provider": "OpenAI"
  },
  {
    "display_name": "o4 Mini",
    "model_name": "o4-mini",
    "provider": "OpenAI"
  }
];

// Find the Gemini 2.5 Flash model to use as default
export const defaultModel = apiModels.find(model => model.model_name === "gemini-2.5-flash-preview-05-20") || null; 