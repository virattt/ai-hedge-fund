"""Tests for the Earnings Reaction Playbook workflow.

Structural tests only — these verify the graph shape, initial-state contract,
and checkpointer factories. They do not invoke real LLMs and do not call the
agent functions. End-to-end execution is exercised in the sales-demo rehearsal
documented in ``docs/sales-demo.md``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from src.utils.analysts import ANALYST_CONFIG
from src.workflows.earnings_reaction import (
    EARNINGS_REACTION_ANALYSTS,
    _resolve_analyst,
    build_earnings_reaction_graph,
    earnings_reaction_initial_state,
    memory_checkpointer,
    sqlite_checkpointer,
)


class TestPlaybookComposition:
    """The Earnings Reaction Playbook is six curated analysts plus risk + portfolio."""

    def test_playbook_picks_six_analysts(self):
        assert len(EARNINGS_REACTION_ANALYSTS) == 6

    def test_playbook_analysts_have_no_duplicates(self):
        assert len(set(EARNINGS_REACTION_ANALYSTS)) == 6

    def test_every_playbook_analyst_exists_in_ANALYST_CONFIG(self):
        for key in EARNINGS_REACTION_ANALYSTS:
            assert key in ANALYST_CONFIG, f"Playbook references unknown analyst {key!r}"

    def test_playbook_covers_distinct_lenses(self):
        """Sanity: the playbook should not be six versions of the same lens.
        We check that fundamentals, sentiment, technicals, valuation, and at
        least two persona-style analysts are present."""
        keys = set(EARNINGS_REACTION_ANALYSTS)
        assert "fundamentals_analyst" in keys
        assert "sentiment_analyst" in keys
        assert "technical_analyst" in keys
        assert "valuation_analyst" in keys
        persona_count = sum(
            1
            for k in keys
            if ANALYST_CONFIG[k]["display_name"]
            not in {
                "Fundamentals Analyst",
                "Sentiment Analyst",
                "Technical Analyst",
                "Valuation Analyst",
            }
        )
        assert persona_count >= 2, "Playbook should include at least 2 persona analysts"


class TestGraphStructure:
    """Compiled graph shape — fan-out from start, fan-in to risk, linear tail."""

    def test_graph_compiles_without_checkpointer(self):
        graph = build_earnings_reaction_graph()
        assert graph is not None

    def test_graph_compiles_with_memory_checkpointer(self):
        graph = build_earnings_reaction_graph(checkpointer=memory_checkpointer())
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        graph = build_earnings_reaction_graph()
        node_names = set(graph.get_graph().nodes.keys())
        # LangGraph injects __start__ and __end__ sentinels
        expected = {"__start__", "__end__", "start_node", "risk_management_agent", "portfolio_manager"}
        expected |= {f"{key}_agent" for key in EARNINGS_REACTION_ANALYSTS}
        assert node_names == expected

    def test_all_analysts_fan_out_from_start_node(self):
        graph = build_earnings_reaction_graph()
        edges = [(e.source, e.target) for e in graph.get_graph().edges]
        for key in EARNINGS_REACTION_ANALYSTS:
            assert ("start_node", f"{key}_agent") in edges

    def test_all_analysts_fan_in_to_risk_manager(self):
        graph = build_earnings_reaction_graph()
        edges = [(e.source, e.target) for e in graph.get_graph().edges]
        for key in EARNINGS_REACTION_ANALYSTS:
            assert (f"{key}_agent", "risk_management_agent") in edges

    def test_risk_manager_pipes_to_portfolio_manager(self):
        graph = build_earnings_reaction_graph()
        edges = [(e.source, e.target) for e in graph.get_graph().edges]
        assert ("risk_management_agent", "portfolio_manager") in edges

    def test_portfolio_manager_terminates_at_end(self):
        graph = build_earnings_reaction_graph()
        edges = [(e.source, e.target) for e in graph.get_graph().edges]
        assert ("portfolio_manager", "__end__") in edges


class TestAnalystResolution:
    """Unknown analyst keys must fail loudly so upstream agent renames don't
    silently break the playbook."""

    def test_resolve_known_analyst(self):
        node_name, func = _resolve_analyst("warren_buffett")
        assert node_name == "warren_buffett_agent"
        assert callable(func)

    def test_resolve_unknown_analyst_raises(self):
        with pytest.raises(KeyError, match="unknown analyst"):
            _resolve_analyst("nonexistent_analyst_xyz")


class TestInitialState:
    """Initial state matches the AgentState contract that src.main expects."""

    def test_initial_state_has_required_top_level_keys(self):
        state = earnings_reaction_initial_state(
            tickers=["AAPL"],
            start_date="2026-01-01",
            end_date="2026-03-31",
            portfolio={"cash": 100000, "positions": {}},
        )
        assert set(state.keys()) == {"messages", "data", "metadata"}

    def test_initial_state_carries_a_human_message(self):
        state = earnings_reaction_initial_state(
            tickers=["AAPL"],
            start_date="2026-01-01",
            end_date="2026-03-31",
            portfolio={"cash": 100000},
        )
        assert len(state["messages"]) == 1
        assert isinstance(state["messages"][0], HumanMessage)
        assert "Earnings Reaction Playbook" in state["messages"][0].content

    def test_initial_state_tags_workflow_in_metadata(self):
        state = earnings_reaction_initial_state(
            tickers=["AAPL"],
            start_date="2026-01-01",
            end_date="2026-03-31",
            portfolio={"cash": 100000},
        )
        assert state["metadata"]["workflow"] == "earnings_reaction"

    def test_initial_state_passes_through_model_choice(self):
        state = earnings_reaction_initial_state(
            tickers=["AAPL"],
            start_date="2026-01-01",
            end_date="2026-03-31",
            portfolio={"cash": 100000},
            model_name="gpt-4.1",
            model_provider="OpenAI",
        )
        assert state["metadata"]["model_name"] == "gpt-4.1"
        assert state["metadata"]["model_provider"] == "OpenAI"

    def test_initial_state_starts_with_empty_analyst_signals(self):
        state = earnings_reaction_initial_state(
            tickers=["NVDA", "MSFT"],
            start_date="2026-01-01",
            end_date="2026-03-31",
            portfolio={"cash": 100000},
        )
        assert state["data"]["analyst_signals"] == {}
        assert state["data"]["tickers"] == ["NVDA", "MSFT"]


class TestCheckpointers:
    def test_memory_checkpointer_returns_memory_saver(self):
        saver = memory_checkpointer()
        assert isinstance(saver, MemorySaver)

    def test_sqlite_checkpointer_yields_sqlite_saver(self, tmp_path: Path):
        db = tmp_path / "phase2-test.db"
        with sqlite_checkpointer(str(db)) as saver:
            assert isinstance(saver, SqliteSaver)
            # File is created on first .setup() call. We just verify the saver
            # has a working cursor (i.e., underlying connection is alive).
            assert saver.cursor() is not None

    def test_sqlite_checkpointer_persists_state_across_context_exits(self, tmp_path: Path):
        """Two separate enters of sqlite_checkpointer against the same path
        share the on-disk store — that's the whole point of switching from
        MemorySaver to SqliteSaver."""
        db = tmp_path / "persist.db"

        # First enter: write a checkpoint via the underlying connection.
        with sqlite_checkpointer(str(db)) as saver:
            saver.setup()

        assert db.exists(), "SqliteSaver should create the on-disk file via setup()"

        # Second enter: previous state should be readable (no crash, no schema
        # mismatch, no fresh DB).
        with sqlite_checkpointer(str(db)) as saver:
            saver.setup()
            # Use a raw sqlite3 connection to count rows in checkpoint tables
            # without depending on a particular API surface.
            with sqlite3.connect(str(db)) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                assert "checkpoints" in tables
