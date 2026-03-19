from datetime import datetime, timezone
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.style import Style
from rich.text import Text
from typing import Dict, Optional, Callable, List
import time
import sys

# Use stdout for progress display, leave stderr for logging
console = Console(file=sys.stdout)


class AgentProgress:
    """Manages progress tracking for multiple agents."""

    def __init__(self, min_update_interval: float = 0.5):
        self.agent_status: Dict[str, Dict[str, str]] = {}
        self.table = Table(show_header=False, box=None, padding=(0, 1))
        # redirect_stdout=False: don't intercept print() calls so that
        # output after Live.stop() is not lost or buffered by Rich
        self.live = Live(self.table, console=console, refresh_per_second=4, redirect_stdout=False, redirect_stderr=False)
        self.started = False
        self.update_handlers: List[Callable[[str, Optional[str], str], None]] = []
        self.min_update_interval = min_update_interval  # Minimum seconds between updates for same agent
        self.last_update_time: Dict[str, float] = {}  # Track last update time per agent
        self.pending_updates: Dict[str, Dict] = {}  # Store pending updates that were throttled

    def register_handler(self, handler: Callable[[str, Optional[str], str], None]):
        """Register a handler to be called when agent status updates."""
        self.update_handlers.append(handler)
        return handler  # Return handler to support use as decorator

    def unregister_handler(self, handler: Callable[[str, Optional[str], str], None]):
        """Unregister a previously registered handler."""
        if handler in self.update_handlers:
            self.update_handlers.remove(handler)

    def start(self):
        """Start the progress display."""
        if not self.started:
            self.live.start()
            self.started = True

    def stop(self):
        """Stop the progress display."""
        if self.started:
            # Flush any pending updates before stopping
            self._flush_pending_updates()
            self.live.stop()
            self.started = False

    def _flush_pending_updates(self):
        """Flush any pending updates that were throttled."""
        for agent_name, update_data in list(self.pending_updates.items()):
            # Force update without throttling
            old_interval = self.min_update_interval
            self.min_update_interval = 0
            self.update_status(
                agent_name,
                update_data.get("ticker"),
                update_data.get("status"),
                update_data.get("analysis")
            )
            self.min_update_interval = old_interval
        self.pending_updates.clear()

    def update_status(self, agent_name: str, ticker: Optional[str] = None, status: str = "", analysis: Optional[str] = None):
        """Update the status of an agent with throttling to reduce noise."""
        current_time = time.time()

        # Check if this is a significant status update (Done or Error always show immediately)
        is_final_status = status.lower() in ["done", "error"]

        # Check if enough time has passed since last update for this agent
        last_update = self.last_update_time.get(agent_name, 0)
        time_since_update = current_time - last_update
        should_update = is_final_status or time_since_update >= self.min_update_interval

        if not should_update:
            # Store as pending update - will be shown if it's the last one
            self.pending_updates[agent_name] = {
                "ticker": ticker,
                "status": status,
                "analysis": analysis,
                "time": current_time
            }
            return

        # Clear any pending updates for this agent
        self.pending_updates.pop(agent_name, None)

        if agent_name not in self.agent_status:
            self.agent_status[agent_name] = {"status": "", "ticker": None}

        if ticker:
            self.agent_status[agent_name]["ticker"] = ticker
        if status:
            self.agent_status[agent_name]["status"] = status
        if analysis:
            self.agent_status[agent_name]["analysis"] = analysis

        # Set the timestamp as UTC datetime
        timestamp = datetime.now(timezone.utc).isoformat()
        self.agent_status[agent_name]["timestamp"] = timestamp

        # Update last update time
        self.last_update_time[agent_name] = current_time

        # Notify all registered handlers
        for handler in self.update_handlers:
            handler(agent_name, ticker, status, analysis, timestamp)

        self._refresh_display()

    def get_all_status(self):
        """Get the current status of all agents as a dictionary."""
        return {agent_name: {"ticker": info["ticker"], "status": info["status"], "display_name": self._get_display_name(agent_name)} for agent_name, info in self.agent_status.items()}

    def _get_display_name(self, agent_name: str) -> str:
        """Convert agent_name to a display-friendly format."""
        return agent_name.replace("_agent", "").replace("_", " ").title()

    def _refresh_display(self):
        """Refresh the progress display."""
        self.table.columns.clear()
        self.table.add_column(width=100)

        # Sort agents with Risk Management and Portfolio Management at the bottom
        def sort_key(item):
            agent_name = item[0]
            if "risk_management" in agent_name:
                return (2, agent_name)
            elif "portfolio_management" in agent_name:
                return (3, agent_name)
            else:
                return (1, agent_name)

        for agent_name, info in sorted(self.agent_status.items(), key=sort_key):
            status = info["status"]
            ticker = info["ticker"]
            # Create the status text with appropriate styling
            if status.lower() == "done":
                style = Style(color="green", bold=True)
                symbol = "✓"
            elif status.lower() == "error":
                style = Style(color="red", bold=True)
                symbol = "✗"
            else:
                style = Style(color="yellow")
                symbol = "⋯"

            agent_display = self._get_display_name(agent_name)
            status_text = Text()
            status_text.append(f"{symbol} ", style=style)
            status_text.append(f"{agent_display:<20}", style=Style(bold=True))

            if ticker:
                status_text.append(f"[{ticker}] ", style=Style(color="cyan"))
            status_text.append(status, style=style)

            self.table.add_row(status_text)


# Create a global instance
progress = AgentProgress()
