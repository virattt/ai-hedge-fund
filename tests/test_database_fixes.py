"""Tests for database fixes -- WAL pragma, UniqueConstraint, bulk transaction atomicity.

We mock heavy transitive imports (langchain) to avoid needing those
packages installed in the test environment.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

# -----------------------------------------------------------------------
# Stub out heavy transitive imports before importing project modules
# -----------------------------------------------------------------------
_STUB_NAMES = [
    "langchain_core",
    "langchain_core.messages",
    "langgraph",
    "langgraph.graph",
    "langchain_anthropic",
    "langchain_openai",
    "langchain_groq",
    "langchain_deepseek",
    "langchain_ollama",
    "langchain_google_genai",
    "langchain_gigachat",
    "langchain_xai",
    "langchain",
    "langchain.chat_models",
    "langchain_community",
    "langchain_community.chat_models",
]

for _name in _STUB_NAMES:
    if _name not in sys.modules:
        sys.modules[_name] = ModuleType(_name)

# Provide minimal stubs so downstream imports don't fail
sys.modules["langchain_core.messages"].HumanMessage = type("HumanMessage", (), {})
sys.modules["langgraph.graph"].END = "END"
sys.modules["langgraph.graph"].StateGraph = MagicMock

# Stub out graph module to prevent its heavy imports
_graph_mod = ModuleType("app.backend.services.graph")
_graph_mod.run_graph_async = MagicMock()
_graph_mod.parse_hedge_fund_response = MagicMock(return_value={})
_graph_mod.extract_base_agent_key = lambda x: x
sys.modules["app.backend.services.graph"] = _graph_mod

_schemas_mod = ModuleType("app.backend.models.schemas")
_schemas_mod.FlowRunStatus = type(
    "FlowRunStatus",
    (),
    {
        "IDLE": type("StatusValue", (), {"value": "IDLE"})(),
        "IN_PROGRESS": type("StatusValue", (), {"value": "IN_PROGRESS"})(),
        "COMPLETE": type("StatusValue", (), {"value": "COMPLETE"})(),
        "ERROR": type("StatusValue", (), {"value": "ERROR"})(),
    },
)
sys.modules["app.backend.models.schemas"] = _schemas_mod

# Now safe to import project modules
from app.backend.database.connection import Base, set_sqlite_pragma
from app.backend.database.models import ApiKey, HedgeFundFlow, HedgeFundFlowRun
from app.backend.repositories.api_key_repository import ApiKeyRepository
from app.backend.repositories.flow_run_repository import FlowRunRepository


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """In-memory SQLite session with tables created."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# -----------------------------------------------------------------------
# 1. WAL Pragma Tests
# -----------------------------------------------------------------------

def test_sqlite_wal_pragma_is_enabled_for_sqlite_connections(tmp_path):
    """WAL and busy_timeout should be set via set_sqlite_pragma on a file-backed DB."""
    db_path = tmp_path / "wal_test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", set_sqlite_pragma)

    try:
        with engine.connect() as connection:
            journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar()
            busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar()
    finally:
        engine.dispose()

    assert journal_mode.lower() == "wal"
    assert busy_timeout == 5000


# -----------------------------------------------------------------------
# 2. UniqueConstraint Tests
# -----------------------------------------------------------------------

def test_flow_run_unique_constraint_raises_integrity_error(db_session):
    """Inserting two runs with the same (flow_id, run_number) must raise IntegrityError."""
    flow = HedgeFundFlow(name="test-flow", nodes=[], edges=[])
    db_session.add(flow)
    db_session.commit()
    db_session.refresh(flow)

    db_session.add_all([
        HedgeFundFlowRun(flow_id=flow.id, run_number=1, status="IDLE"),
        HedgeFundFlowRun(flow_id=flow.id, run_number=1, status="IDLE"),
    ])

    with pytest.raises(IntegrityError):
        db_session.commit()


# -----------------------------------------------------------------------
# 3. Bulk Transaction Atomicity Tests
# -----------------------------------------------------------------------

def test_bulk_create_or_update_rolls_back_all_changes_on_error(db_session):
    """If any item in a bulk operation fails, the entire batch is rolled back."""
    repo = ApiKeyRepository(db_session)

    with pytest.raises(IntegrityError):
        repo.bulk_create_or_update([
            {"provider": "OPENAI_API_KEY", "key_value": "valid-key"},
            {"provider": "ANTHROPIC_API_KEY", "key_value": None},  # NOT NULL violation
        ])

    assert db_session.query(ApiKey).count() == 0


# -----------------------------------------------------------------------
# 4. FlowRunRepository retry logic
# -----------------------------------------------------------------------

def test_create_flow_run_retries_after_integrity_error():
    """create_flow_run should retry with a new run_number on IntegrityError."""
    db = MagicMock()
    db.commit.side_effect = [
        IntegrityError("INSERT", {"flow_id": 7}, Exception("duplicate")),
        None,
    ]
    repo = FlowRunRepository(db)

    with patch.object(repo, "_get_next_run_number", side_effect=[1, 2]) as mock_next:
        flow_run = repo.create_flow_run(flow_id=7, request_data={"tickers": ["AAPL"]})

    assert flow_run.flow_id == 7
    assert flow_run.run_number == 2
    assert db.add.call_count == 2
    assert db.commit.call_count == 2
    db.rollback.assert_called_once()
    db.refresh.assert_called_once_with(flow_run)
    assert mock_next.call_count == 2
