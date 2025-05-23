import { type ModelProvider } from "@/data/models";

export enum HedgeFundModelProvider {
  OPENAI = "OPENAI",
  ANTHROPIC = "ANTHROPIC",
  GOOGLE = "GOOGLE",
  AZURE = "AZURE"
}

export const modelProviderToHedgeFundModelProvider = (model: ModelProvider | undefined): HedgeFundModelProvider | undefined => {
  switch (model) {
    case "OpenAI":
      return HedgeFundModelProvider.OPENAI;
    case "Anthropic":
      return HedgeFundModelProvider.ANTHROPIC;
    default:
      return undefined;
  }
}