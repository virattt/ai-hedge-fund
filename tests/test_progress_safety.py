import pytest
import threading

from src.utils.progress import AgentProgress


class TestAgentProgress:
    """Test AgentProgress handler registration and status updates."""

    def test_register_unregister(self):
        p = AgentProgress()
        handler = lambda *args: None
        p.register_handler(handler)
        assert handler in p.update_handlers
        p.unregister_handler(handler)
        assert handler not in p.update_handlers

    def test_reset_clears_status(self):
        p = AgentProgress()
        p.update_status("agent1", ticker="AAPL", status="analyzing")
        assert "agent1" in p.agent_status
        p.reset()
        assert len(p.agent_status) == 0

    def test_unregister_nonexistent_handler(self):
        """Unregistering a handler that was never registered should not raise."""
        p = AgentProgress()
        handler = lambda *args: None
        p.unregister_handler(handler)  # should not raise

    def test_concurrent_register_unregister(self):
        """Concurrent register/unregister must not raise."""
        p = AgentProgress()
        errors = []
        handlers = []
        lock = threading.Lock()

        def register_worker():
            try:
                h = lambda *args: None
                p.register_handler(h)
                with lock:
                    handlers.append(h)
            except Exception as e:
                errors.append(e)

        def unregister_worker():
            try:
                with lock:
                    if handlers:
                        h = handlers.pop(0)
                    else:
                        return
                p.unregister_handler(h)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(20):
            threads.append(threading.Thread(target=register_worker))
            threads.append(threading.Thread(target=unregister_worker))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_updates(self):
        """Concurrent update_status calls must not raise."""
        p = AgentProgress()
        errors = []

        def updater(n):
            try:
                for i in range(20):
                    p.update_status(f"agent_{n}", ticker="AAPL", status=f"step_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=updater, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_handler_called_on_update(self):
        """Registered handler receives correct arguments on update_status."""
        p = AgentProgress()
        calls = []

        def handler(agent_name, ticker, status, analysis, timestamp):
            calls.append((agent_name, ticker, status, analysis, timestamp))

        p.register_handler(handler)
        p.update_status("agent1", ticker="AAPL", status="done")
        assert len(calls) == 1
        assert calls[0][0] == "agent1"
        assert calls[0][1] == "AAPL"
        assert calls[0][2] == "done"
        assert calls[0][3] is None  # analysis not provided
        assert calls[0][4] is not None  # timestamp should be set

    def test_multiple_handlers_all_called(self):
        """All registered handlers are invoked on each update."""
        p = AgentProgress()
        call_counts = {"a": 0, "b": 0}

        def handler_a(*args):
            call_counts["a"] += 1

        def handler_b(*args):
            call_counts["b"] += 1

        p.register_handler(handler_a)
        p.register_handler(handler_b)
        p.update_status("agent1", status="running")
        assert call_counts["a"] == 1
        assert call_counts["b"] == 1

    def test_update_status_accumulates_agents(self):
        """Each unique agent_name creates a separate entry."""
        p = AgentProgress()
        p.update_status("agent_a", status="running")
        p.update_status("agent_b", status="done")
        assert "agent_a" in p.agent_status
        assert "agent_b" in p.agent_status
        assert p.agent_status["agent_a"]["status"] == "running"
        assert p.agent_status["agent_b"]["status"] == "done"
