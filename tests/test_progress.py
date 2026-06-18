import pytest
import threading

from src.utils.progress import AgentProgress


class TestAgentProgress:
    """Test AgentProgress handler management and thread safety."""

    def test_register_handler(self):
        p = AgentProgress()
        handler = lambda *args: None
        p.register_handler(handler)
        assert handler in p.update_handlers

    def test_unregister_handler(self):
        p = AgentProgress()
        handler = lambda *args: None
        p.register_handler(handler)
        p.unregister_handler(handler)
        assert handler not in p.update_handlers

    def test_unregister_nonexistent_handler_is_safe(self):
        p = AgentProgress()
        handler = lambda *args: None
        p.unregister_handler(handler)  # should not raise

    def test_reset_clears_status(self):
        p = AgentProgress()
        p.update_status("agent1", "AAPL", "analyzing")
        assert "agent1" in p.agent_status
        p.reset()
        assert len(p.agent_status) == 0

    def test_update_status_notifies_handlers(self):
        p = AgentProgress()
        received = []
        handler = lambda *args: received.append(args)
        p.register_handler(handler)
        p.update_status("agent1", "AAPL", "done", "bullish")
        assert len(received) == 1
        agent_name, ticker, status, analysis, timestamp = received[0]
        assert agent_name == "agent1"
        assert ticker == "AAPL"
        assert status == "done"
        assert analysis == "bullish"
        assert timestamp is not None

    def test_handler_not_called_after_unregister(self):
        p = AgentProgress()
        received = []
        handler = lambda *args: received.append(args)
        p.register_handler(handler)
        p.unregister_handler(handler)
        p.update_status("agent1", "AAPL", "done")
        assert len(received) == 0

    def test_concurrent_updates(self):
        """Concurrent update_status calls do not raise."""
        p = AgentProgress()
        errors = []

        def updater(n):
            try:
                for i in range(20):
                    p.update_status(f"agent_{n}", "AAPL", f"step_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=updater, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_register_unregister(self):
        """Concurrent handler registration/unregistration does not raise."""
        p = AgentProgress()
        errors = []

        def register_cycle(n):
            try:
                handler = lambda *args: None
                for _ in range(20):
                    p.register_handler(handler)
                    p.unregister_handler(handler)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_cycle, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
