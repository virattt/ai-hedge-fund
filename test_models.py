#!/usr/bin/env python3
"""Test script to verify all model integrations are working properly."""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.llm.models import get_model, ModelProvider, get_model_info

# Load environment variables
load_dotenv()

def test_model(model_name: str, provider: ModelProvider, test_prompt: str = "Say 'Hello, World!' in exactly 3 words."):
    """Test a specific model integration."""
    print(f"\n{'='*60}")
    print(f"Testing {provider.value} - {model_name}")
    print(f"{'='*60}")
    
    try:
        # Get model info
        model_info = get_model_info(model_name, provider.value)
        if model_info:
            print(f"Model Info: {model_info.display_name}")
        
        # Get the model
        model = get_model(model_name, provider)
        
        # Test the model
        response = model.invoke(test_prompt)
        print(f"Response: {response.content}")
        print("✅ Success!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(f"Make sure the required API key is set in your .env file")

def main():
    """Test all configured models."""
    print("Testing AI Hedge Fund Model Integrations")
    print("=" * 60)
    
    # Test Azure OpenAI (if configured)
    if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_BASE_URL"):
        test_model("gpt-4o", ModelProvider.OPENAI)
    elif os.getenv("OPENAI_API_KEY"):
        # Test regular OpenAI
        test_model("gpt-4o", ModelProvider.OPENAI)
    
    # Test Google Gemini
    if os.getenv("GOOGLE_API_KEY"):
        test_model("gemini-2.5-flash-preview-05-20", ModelProvider.GEMINI)
    
    # Test DeepSeek (API)
    if os.getenv("DEEPSEEK_API_KEY"):
        test_model("deepseek-chat", ModelProvider.DEEPSEEK)
    
    # Test Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        test_model("claude-3-5-haiku-latest", ModelProvider.ANTHROPIC)
    
    # Test Groq
    if os.getenv("GROQ_API_KEY"):
        test_model("meta-llama/llama-4-scout-17b-16e-instruct", ModelProvider.GROQ)
    
    # Test Ollama models
    print("\n" + "="*60)
    print("Testing Ollama Models (requires Ollama to be running)")
    print("="*60)
    
    # Test DeepSeek-R1 via Ollama
    try:
        test_model("deepseek-r1:latest", ModelProvider.OLLAMA)
    except Exception as e:
        print(f"❌ DeepSeek-R1 via Ollama: {str(e)}")
        print("Make sure Ollama is running and deepseek-r1 model is pulled")
    
    print("\n" + "="*60)
    print("Model Integration Testing Complete!")
    print("="*60)

if __name__ == "__main__":
    main()