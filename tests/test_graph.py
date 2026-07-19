"""Regression tests for create_graph edge-wiring correctness (bug #635).

Uses importlib to load graph.py directly so we don't need the full project
installed; project-internal modules (src.*, app.*) are stubbed via sys.modules
before the load; third-party packages (langgraph, langchain_core) are the real
installed versions.
"""

import sys
import types
import importlib.util
from types import SimpleNamespace
from pathlib import Path
from typing import TypedDict
from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Stub project-internal modules ONLY (NOT langgraph / langchain_core).
# They must be registered before graph.py is executed.
# ---------------------------------------------------------------------------

def _pkg(path: str):
    mod = types.ModuleType(path)
    mod.__path__ = []
    mod.__package__ = path
    sys.modules[path] = mod
    return mod


def _mod(path: str, **attrs):
    mod = types.ModuleType(path)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[path] = mod
    return mod


for _p in ("src", "src.agents", "src.utils", "src.graph",
           "app", "app.backend", "app.backend.services"):
    _pkg(_p)

_mod("src.agents.portfolio_manager",
     portfolio_management_agent=MagicMock(name="pm_agent"))
_mod("src.agents.risk_manager",
     risk_management_agent=MagicMock(name="rm_agent"))
_mod("src.main", start=MagicMock(name="start"))
class _AgentState(TypedDict):
    messages: list

_mod("src.graph.state", AgentState=_AgentState)
_mod("src.utils.analysts", ANALYST_CONFIG={})
_mod("app.backend.services.agent_service",
     create_agent_function=MagicMock(
         side_effect=lambda fn, nid: MagicMock(name=f"agent_{nid}")))

# Now import the real langgraph (langchain_core is a real installed dep).
from langgraph.graph import StateGraph  # noqa: E402

# Load graph.py directly without going through the package machinery.
_GRAPH_FILE = (
    Path(__file__).parent.parent / "app" / "backend" / "services" / "graph.py"
)
_spec = importlib.util.spec_from_file_location("_graph_under_test", _GRAPH_FILE)
_graph_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_graph_mod)
create_graph = _graph_mod.create_graph


# ---------------------------------------------------------------------------
# Minimal ANALYST_CONFIG for tests
# ---------------------------------------------------------------------------

TEST_CONFIG = {
    "warren_buffett": {"agent_func": MagicMock()},
    "fundamentals_analyst": {"agent_func": MagicMock()},
    "portfolio_manager": {"agent_func": MagicMock()},
}


def _node(nid: str): return SimpleNamespace(id=nid)
def _edge(src: str, tgt: str): return SimpleNamespace(source=src, target=tgt)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateGraphUnknownNode:
    """Regression tests for the unknown-node edge crash (GitHub issue #635)."""

    def test_edge_from_unknown_frontend_node_does_not_raise(self):
        """
        A React Flow 'stock-analyzer' visual node is not in ANALYST_CONFIG, so
        create_graph skips it during add_node().  Before the fix its ID was
        still forwarded to add_edge(), raising:

            ValueError: Found edge starting at unknown node 'stock-analyzer-node_t4jxmp'

        After the fix, only edges between *registered* nodes are wired.
        """
        analyst_id = "warren_buffett_abc123"
        pm_id      = "portfolio_manager_xyz999"
        unknown_id = "stock-analyzer-node_t4jxmp"

        nodes = [_node(analyst_id), _node(pm_id), _node(unknown_id)]
        edges = [
            _edge(unknown_id, analyst_id),   # was triggering the crash
            _edge(analyst_id, pm_id),
        ]

        with patch.object(_graph_mod, "ANALYST_CONFIG", TEST_CONFIG):
            graph = create_graph(nodes, edges)
            # compile() is where langgraph validates edge connectivity;
            # it raises ValueError if any edge references an unknown node.
            graph.compile()  # must not raise

        assert isinstance(graph, StateGraph)

    def test_edge_to_unknown_frontend_node_does_not_raise(self):
        """Edges where the *target* is unregistered are also dropped cleanly."""
        analyst_id = "fundamentals_analyst_aaa111"
        pm_id      = "portfolio_manager_bbb222"
        unknown_id = "stock-analyzer-node_ccc333"

        nodes = [_node(analyst_id), _node(pm_id), _node(unknown_id)]
        edges = [
            _edge(analyst_id, unknown_id),   # target not registered
            _edge(analyst_id, pm_id),
        ]

        with patch.object(_graph_mod, "ANALYST_CONFIG", TEST_CONFIG):
            graph = create_graph(nodes, edges)
            graph.compile()  # must not raise

        assert isinstance(graph, StateGraph)

    def test_all_valid_nodes_graph_unchanged(self):
        """Sanity: a graph with only ANALYST_CONFIG nodes still compiles correctly."""
        analyst_id = "warren_buffett_abc123"
        pm_id      = "portfolio_manager_xyz999"

        nodes = [_node(analyst_id), _node(pm_id)]
        edges = [_edge(analyst_id, pm_id)]

        with patch.object(_graph_mod, "ANALYST_CONFIG", TEST_CONFIG):
            graph = create_graph(nodes, edges)
            graph.compile()  # must not raise

        assert isinstance(graph, StateGraph)
