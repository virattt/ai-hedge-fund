export interface ModelItem {
  display_name: string;
  model_name: string;
  provider: "Anthropic" | "DeepSeek" | "Gemini" | "Groq" | "OpenAI";
}

export const apiModels: ModelItem[] = [
  {
    "display_name": "claude-3.5-haiku",
    "model_name": "claude-3-5-haiku-latest",
    "provider": "Anthropic"
  },
  {
    "display_name": "claude-3.7-sonnet",
    "model_name": "claude-3-7-sonnet-latest",
    "provider": "Anthropic"
  },
  {
    "display_name": "deepseek-r1",
    "model_name": "deepseek-reasoner",
    "provider": "DeepSeek"
  },
  {
    "display_name": "deepseek-v3",
    "model_name": "deepseek-chat",
    "provider": "DeepSeek"
  },
  {
    "display_name": "gemini-2.0-flash",
    "model_name": "gemini-2.0-flash",
    "provider": "Gemini"
  },
  {
    "display_name": "gemini-2.5-pro",
    "model_name": "gemini-2.5-pro-exp-03-25",
    "provider": "Gemini"
  },
  {
    "display_name": "llama-4-scout-17b",
    "model_name": "meta-llama/llama-4-scout-17b-16e-instruct",
    "provider": "Groq"
  },
  {
    "display_name": "llama-4-maverick-17b",
    "model_name": "meta-llama/llama-4-maverick-17b-128e-instruct",
    "provider": "Groq"
  },
  {
    "display_name": "gpt-4.5",
    "model_name": "gpt-4.5-preview",
    "provider": "OpenAI"
  },
  {
    "display_name": "gpt-4o",
    "model_name": "gpt-4o",
    "provider": "OpenAI"
  },
  {
    "display_name": "o3",
    "model_name": "o3",
    "provider": "OpenAI"
  },
  {
    "display_name": "o4-mini",
    "model_name": "o4-mini",
    "provider": "OpenAI"
  }
];

// Find the GPT-4o model to use as default
export const defaultModel = apiModels.find(model => model.model_name === "gpt-4o") || null; 