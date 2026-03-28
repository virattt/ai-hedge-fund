"""Tests for graph state utilities in src/graph/state.py.

Tests merge_dicts, show_agent_reasoning, and the convert_to_serializable helper.
"""

import json
from io import StringIO
from unittest.mock import patch

import pandas as pd

from src.graph.state import merge_dicts, show_agent_reasoning


class TestMergeDicts:
    def test_basic_merge(self):
        assert merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_second_overwrites_first(self):
        assert merge_dicts({"a": 1}, {"a": 2}) == {"a": 2}

    def test_empty_dicts(self):
        assert merge_dicts({}, {}) == {}

    def test_one_empty(self):
        assert merge_dicts({"a": 1}, {}) == {"a": 1}
        assert merge_dicts({}, {"b": 2}) == {"b": 2}

    def test_nested_values_not_deep_merged(self):
        """merge_dicts is shallow — nested dicts are replaced, not merged."""
        result = merge_dicts({"x": {"a": 1, "b": 2}}, {"x": {"a": 99}})
        assert result == {"x": {"a": 99}}  # b is gone — shallow merge


class TestShowAgentReasoning:
    """Test output formatting of show_agent_reasoning."""

    def test_dict_output(self, capsys):
        show_agent_reasoning({"signal": "bullish", "confidence": 0.9}, "Test Agent")
        captured = capsys.readouterr()
        assert "Test Agent" in captured.out
        assert "bullish" in captured.out

    def test_list_output(self, capsys):
        show_agent_reasoning([{"ticker": "AAPL", "signal": "buy"}], "Test Agent")
        captured = capsys.readouterr()
        assert "AAPL" in captured.out
        assert "buy" in captured.out

    def test_json_string_output(self, capsys):
        json_str = json.dumps({"key": "value"})
        show_agent_reasoning(json_str, "Test Agent")
        captured = capsys.readouterr()
        assert "value" in captured.out

    def test_plain_string_output(self, capsys):
        show_agent_reasoning("This is not JSON", "Test Agent")
        captured = capsys.readouterr()
        assert "This is not JSON" in captured.out

    def test_pandas_series_in_dict(self, capsys):
        """Tests convert_to_serializable handling of pandas objects."""
        series = pd.Series({"a": 1, "b": 2})
        show_agent_reasoning({"data": series}, "Test Agent")
        captured = capsys.readouterr()
        # Should convert to dict representation without error
        assert "a" in captured.out

    def test_custom_object_in_dict(self, capsys):
        class CustomObj:
            def __init__(self):
                self.value = 42

        show_agent_reasoning({"obj": CustomObj()}, "Test Agent")
        captured = capsys.readouterr()
        assert "42" in captured.out

    def test_nested_list_in_dict(self, capsys):
        data = {"signals": [{"sig": "buy"}, {"sig": "sell"}]}
        show_agent_reasoning(data, "Test Agent")
        captured = capsys.readouterr()
        assert "buy" in captured.out
        assert "sell" in captured.out
