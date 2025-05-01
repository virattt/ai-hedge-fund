from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.style import Style
from rich.text import Text
from typing import Dict, Optional, Tuple, Any
from threading import Lock
import contextlib

console = Console()


class AgentProgress:
    """Manages progress tracking for multiple agents.
    
    This class provides a thread-safe way to display and update the progress
    of different agents in a rich console interface.
    
    Example:
        >>> progress = AgentProgress()
        >>> with progress:  # Using context manager to handle start/stop
        ...     progress.update_status('warren_buffett', 'AAPL', 'Analyzing...')
        ...     # Do work
        ...     progress.update_status('warren_buffett', 'AAPL', 'Done')
    
    Thread Safety:
        All update methods are protected with a lock to ensure thread-safety.
    """

    # Define common styles as class attributes to avoid recreation
    SUCCESS_STYLE: Style = Style(color="green", bold=True)
    ERROR_STYLE: Style = Style(color="red", bold=True)
    PENDING_STYLE: Style = Style(color="yellow")
    AGENT_NAME_STYLE: Style = Style(bold=True)
    TICKER_STYLE: Style = Style(color="cyan")

    def __init__(self) -> None:
        """Initialize the progress tracker."""
        self.agent_status: Dict[str, Dict[str, Any]] = {}
        self.table = Table(show_header=False, box=None, padding=(0, 1))
        # Get the terminal width to set a more dynamic column width
        terminal_width = console.width or 100
        self.table.add_column(width=min(terminal_width - 2, 100))
        self.live = Live(self.table, console=console, refresh_per_second=4)
        self.started = False
        self.lock = Lock()

    def __enter__(self) -> 'AgentProgress':
        """Context manager entry point."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit point."""
        self.stop()

    def start(self) -> None:
        """Start the progress display safely."""
        with self.lock:
            if not self.started:
                try:
                    self.live.start()
                    self.started = True
                except Exception as e:
                    console.print(f"[red]Error starting progress display: {e}[/red]")

    def stop(self) -> None:
        """Stop the progress display safely."""
        with self.lock:
            if self.started:
                try:
                    self.live.stop()
                except Exception as e:
                    console.print(f"[red]Error stopping progress display: {e}[/red]")
                finally:
                    self.started = False

    def update_status(self, agent_name: str, ticker: Optional[str] = None, status: str = "") -> None:
        """Update the status of an agent.
        
        Args:
            agent_name: Name of the agent to update
            ticker: Optional stock ticker the agent is working on
            status: Status message to display
            
        Thread Safety:
            This method is thread-safe and can be called from multiple threads.
        """
        with self.lock:
            if agent_name not in self.agent_status:
                self.agent_status[agent_name] = {"status": "", "ticker": None}

            if ticker is not None:
                self.agent_status[agent_name]["ticker"] = ticker
            if status:
                self.agent_status[agent_name]["status"] = status

            try:
                self._refresh_display()
            except Exception as e:
                console.print(f"[red]Error updating display for {agent_name}: {e}[/red]")

    def _refresh_display(self) -> None:
        """Refresh the progress display with current agent statuses."""
        if not self.started:
            return

        try:
            self.table.columns.clear()
            # Get the terminal width to set a more dynamic column width
            terminal_width = console.width or 100
            self.table.add_column(width=min(terminal_width - 2, 100)) 

            sorted_agents = sorted(
                self.agent_status.items(), 
                key=self._agent_sort_key
            )

            for agent_name, info in sorted_agents:
                status = info["status"]
                ticker = info["ticker"]
                
                # Create the status text with appropriate styling
                status_text = self._format_status(agent_name, ticker, status)
                self.table.add_row(status_text)
        except Exception as e:
            console.print(f"[red]Error refreshing display: {e}[/red]")

    @staticmethod
    def _agent_sort_key(item: Tuple[str, Dict[str, Any]]) -> Tuple[int, str]:
        """Sort key function for ordering agents in the display.
        
        Args:
            item: Tuple of (agent_name, status_dict)
            
        Returns:
            Tuple of (priority, agent_name) where priority is:
                1: Regular agents
                2: Risk management
                3: Portfolio management
        """
        agent_name, _ = item
        priority = 1  # Default priority
        if "risk_management" in agent_name:
            priority = 2
        elif "portfolio_management" in agent_name:
            priority = 3
        return (priority, agent_name)
        
    def _format_status(self, agent_name: str, ticker: Optional[str], status: str) -> Text:
        """Format an agent's status with appropriate styling.
        
        Args:
            agent_name: Name of the agent
            ticker: Stock ticker the agent is working on
            status: Status message
            
        Returns:
            Rich Text object with formatted status
        """
        status_lower = status.lower()
        
        # Select symbol and style based on status
        if status_lower == "done":
            style = self.SUCCESS_STYLE
            symbol = "✓"
        elif status_lower == "error":
            style = self.ERROR_STYLE
            symbol = "✗"
        else:
            style = self.PENDING_STYLE
            symbol = "⋯"

        # Format the agent name for display
        agent_display = agent_name.replace("_agent", "").replace("_", " ").title()
        
        # Build the status text with appropriate styling
        status_text = Text()
        status_text.append(f"{symbol} ", style=style)
        status_text.append(f"{agent_display:<20}", style=self.AGENT_NAME_STYLE)

        if ticker:
            status_text.append(f"[{ticker}] ", style=self.TICKER_STYLE)
        
        status_text.append(status, style=style)
        
        return status_text

    @contextlib.contextmanager
    def task(self, agent_name: str, ticker: Optional[str] = None, task_name: str = "Working") -> None:
        """Context manager for tracking a task's progress.
        
        Example:
            >>> with progress.task('warren_buffett', 'AAPL', 'Analyzing'):
            ...     # Do analysis work
            ...     # On completion, status automatically changes to "Done"
            ...     # On exception, status automatically changes to "Error"
        
        Args:
            agent_name: Name of the agent doing the task
            ticker: Optional stock ticker being worked on
            task_name: Description of the task
        """
        try:
            self.update_status(agent_name, ticker, f"{task_name}...")
            yield
            self.update_status(agent_name, ticker, "Done")
        except Exception as e:
            self.update_status(agent_name, ticker, f"Error: {str(e)[:30]}")
            raise


# Create a global instance - but allow for testing by making it clear this is a singleton
_progress_instance = None

def get_progress() -> AgentProgress:
    """Get the global progress tracker instance."""
    global _progress_instance
    if _progress_instance is None:
        _progress_instance = AgentProgress()
    return _progress_instance

# For backward compatibility
progress = get_progress()