"""
Test for Claude Code adapter to ensure structured output works correctly.

This test replicates the AttributeError issue where AIMessage is returned
instead of a Pydantic model when using with_structured_output().
"""

import pytest
from pydantic import BaseModel, Field
from typing_extensions import Literal
from langchain_core.messages import HumanMessage
from src.llm.claude_code_adapter import ClaudeCodeAdapter


class TestSignal(BaseModel):
    """Test Pydantic model for structured output."""
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


class TestClaudeCodeAdapter:
    """Test suite for ClaudeCodeAdapter."""

    def test_structured_output_returns_pydantic_model(self, monkeypatch):
        """
        Test that with_structured_output() returns a Pydantic model instance,
        not an AIMessage.

        This replicates the error:
        AttributeError: 'AIMessage' object has no attribute 'signal'
        """
        # Mock the CLI response to return JSON
        def mock_query(self, prompt, timeout=None, working_dir=None, model_name=None, output_format=None):
            # When output_format="json", return clean JSON (simulating CLI behavior)
            if output_format == "json":
                return '{"signal": "bullish", "confidence": 85, "reasoning": "Strong fundamentals and growth prospects"}'

            return """
Here's my analysis:

```json
{
    "signal": "bullish",
    "confidence": 85,
    "reasoning": "Strong fundamentals and growth prospects"
}
```
"""

        # Patch the wrapper's query method
        from src.llm.claude_code_wrapper import ClaudeCodeWrapper
        monkeypatch.setattr(ClaudeCodeWrapper, "query", mock_query)

        # Create adapter with structured output
        adapter = ClaudeCodeAdapter()
        structured_adapter = adapter.with_structured_output(TestSignal)

        # Invoke with a test message
        result = structured_adapter.invoke([
            HumanMessage(content="Analyze AAPL")
        ])

        # CRITICAL: Result should be a TestSignal Pydantic model, NOT an AIMessage
        assert isinstance(result, TestSignal), (
            f"Expected TestSignal Pydantic model, got {type(result).__name__}. "
            "This causes: AttributeError: 'AIMessage' object has no attribute 'signal'"
        )

        # Verify we can access Pydantic fields
        assert hasattr(result, 'signal'), "Result missing 'signal' attribute"
        assert hasattr(result, 'confidence'), "Result missing 'confidence' attribute"
        assert hasattr(result, 'reasoning'), "Result missing 'reasoning' attribute"

        # Verify values
        assert result.signal == "bullish"
        assert result.confidence == 85
        assert isinstance(result.reasoning, str)

    def test_structured_output_with_markdown_json(self, monkeypatch):
        """Test parsing JSON from markdown code blocks."""
        def mock_query(self, prompt, timeout=None, working_dir=None, model_name=None, output_format=None):
            # When output_format="json", return clean JSON
            if output_format == "json":
                return '{"signal": "bearish", "confidence": 72, "reasoning": "Overvalued based on P/E ratio"}'

            return """```json
{
    "signal": "bearish",
    "confidence": 72,
    "reasoning": "Overvalued based on P/E ratio"
}
```"""

        from src.llm.claude_code_wrapper import ClaudeCodeWrapper
        monkeypatch.setattr(ClaudeCodeWrapper, "query", mock_query)

        adapter = ClaudeCodeAdapter()
        structured_adapter = adapter.with_structured_output(TestSignal)

        result = structured_adapter.invoke([HumanMessage(content="Test")])

        assert isinstance(result, TestSignal)
        assert result.signal == "bearish"
        assert result.confidence == 72

    def test_structured_output_with_plain_json(self, monkeypatch):
        """Test parsing plain JSON without markdown."""
        def mock_query(self, prompt, timeout=None, working_dir=None, model_name=None, output_format=None):
            return '{"signal": "neutral", "confidence": 50, "reasoning": "Insufficient data"}'

        from src.llm.claude_code_wrapper import ClaudeCodeWrapper
        monkeypatch.setattr(ClaudeCodeWrapper, "query", mock_query)

        adapter = ClaudeCodeAdapter()
        structured_adapter = adapter.with_structured_output(TestSignal)

        result = structured_adapter.invoke([HumanMessage(content="Test")])

        assert isinstance(result, TestSignal)
        assert result.signal == "neutral"

    def test_structured_output_with_malformed_json(self, monkeypatch):
        """Test fallback when JSON is malformed."""
        def mock_query(self, prompt, timeout=None, working_dir=None, model_name=None, output_format=None):
            return "This is not JSON at all"

        from src.llm.claude_code_wrapper import ClaudeCodeWrapper
        monkeypatch.setattr(ClaudeCodeWrapper, "query", mock_query)

        adapter = ClaudeCodeAdapter()
        structured_adapter = adapter.with_structured_output(TestSignal)

        result = structured_adapter.invoke([HumanMessage(content="Test")])

        # Should still return a Pydantic model with defaults
        assert isinstance(result, TestSignal)
        # Default values should be set
        assert result.signal in ["bullish", "bearish", "neutral"]


    def test_normal_invoke_without_structured_output(self, monkeypatch):
        """Test that normal invoke (without structured output) still returns AIMessage."""
        def mock_query(self, prompt, timeout=None, working_dir=None, model_name=None, output_format=None):
            return "Normal text response without JSON"

        from src.llm.claude_code_wrapper import ClaudeCodeWrapper
        monkeypatch.setattr(ClaudeCodeWrapper, "query", mock_query)

        adapter = ClaudeCodeAdapter()
        result = adapter.invoke([HumanMessage(content="Test")])

        # Normal invoke should return AIMessage
        from langchain_core.messages import AIMessage
        assert isinstance(result, AIMessage)
        assert "Normal text response" in result.content

    def test_model_name_passed_to_wrapper(self, monkeypatch):
        """Test that model_name is correctly passed to the wrapper config."""
        from src.llm.claude_code_wrapper import ClaudeCodeWrapper

        def mock_query(self, prompt, timeout=None, working_dir=None, model_name=None, output_format=None):
            return "Test response"

        monkeypatch.setattr(ClaudeCodeWrapper, "query", mock_query)

        # Test with specific model alias (Claude Code uses aliases: sonnet, haiku, opus)
        adapter = ClaudeCodeAdapter(model_name="sonnet")

        # Verify model name is stored in wrapper config
        assert adapter.wrapper.config.model_name == "sonnet"

    def test_default_model_name_is_none(self, monkeypatch):
        """Test that None or empty string means use CLI default (no -m flag)."""
        from src.llm.claude_code_wrapper import ClaudeCodeWrapper

        def mock_query(self, prompt, timeout=None, working_dir=None, model_name=None, output_format=None):
            return "Test response"

        monkeypatch.setattr(ClaudeCodeWrapper, "query", mock_query)

        # Test with None (default)
        adapter1 = ClaudeCodeAdapter(model_name=None)
        assert adapter1.wrapper.config.model_name is None

        # Test with empty string (should also be None)
        adapter2 = ClaudeCodeAdapter()  # Uses default None
        assert adapter2.wrapper.config.model_name is None
