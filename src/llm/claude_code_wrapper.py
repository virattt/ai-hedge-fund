"""
Claude Code CLI Wrapper for AI Hedge Fund.

This wrapper integrates Claude Code CLI (subscription-based) with the AI Hedge Fund,
allowing you to use your Claude Pro Max subscription instead of pay-per-use API.

Features:
- Uses Claude Code CLI (no API key needed, uses subscription)
- Supports one-shot queries and interactive sessions
- Integrates with existing hedge fund infrastructure
- Provides financial analysis tools via prompt engineering

Prerequisites:
1. Install Claude Code CLI:
   npm install -g @anthropic-ai/claude-code
   # OR
   brew install --cask claude-code
   # OR
   curl -fsSL https://claude.ai/install.sh | bash

2. Authenticate (one-time):
   claude /login
   # Opens browser to authenticate with your Claude.ai subscription

Usage:
    from src.llm.claude_code_wrapper import ClaudeCodeAnalyst

    analyst = ClaudeCodeAnalyst()
    result = analyst.analyze("Analyze AAPL fundamentals")
    print(result)
"""

import subprocess
import json
import os
import shutil
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClaudeCodeConfig:
    """Configuration for Claude Code CLI wrapper."""
    cli_path: Optional[str] = None  # Auto-detect if None
    model_name: Optional[str] = None  # Claude model to use (e.g., "sonnet", "haiku", "opus") or None for default cli model
    timeout: int = 60  # Seconds
    max_retries: int = 3
    working_dir: Optional[str] = None


class ClaudeCodeCLIError(Exception):
    """Base exception for Claude Code CLI errors."""
    pass


class ClaudeCodeNotFoundError(ClaudeCodeCLIError):
    """Raised when Claude Code CLI is not installed."""
    pass


class ClaudeCodeAuthError(ClaudeCodeCLIError):
    """Raised when authentication is required."""
    pass


class ClaudeCodeWrapper:
    """
    Wrapper for Claude Code CLI that uses subscription instead of API key.

    This class provides a Python interface to Claude Code CLI, allowing you to:
    - Run one-shot analyses using your subscription
    - Integrate Claude into Python workflows
    - Avoid pay-per-use API costs

    Example:
        >>> wrapper = ClaudeCodeWrapper()
        >>> response = wrapper.query("What is 2+2?")
        >>> print(response)
    """

    def __init__(self, config: Optional[ClaudeCodeConfig] = None):
        """
        Initialize Claude Code CLI wrapper.

        Args:
            config: Configuration options
        """
        self.config = config or ClaudeCodeConfig()

        # Find Claude Code CLI
        self.cli_path = self._find_cli()

        # Verify authentication
        self._check_auth()

    def _find_cli(self) -> str:
        """
        Find Claude Code CLI executable.

        Returns:
            Path to CLI executable

        Raises:
            ClaudeCodeNotFoundError: If CLI is not found
        """
        if self.config.cli_path:
            if not os.path.exists(self.config.cli_path):
                raise ClaudeCodeNotFoundError(
                    f"Claude Code CLI not found at {self.config.cli_path}"
                )
            return self.config.cli_path

        # Try to find in PATH
        cli_path = shutil.which("claude")
        if cli_path:
            return cli_path

        # Common installation paths
        common_paths = [
            "/usr/local/bin/claude",
            "/opt/homebrew/bin/claude",
            os.path.expanduser("~/.local/bin/claude"),
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

        raise ClaudeCodeNotFoundError(
            "Claude Code CLI not found. Install it with:\n"
            "  npm install -g @anthropic-ai/claude-code\n"
            "  OR\n"
            "  brew install --cask claude-code\n"
            "  OR\n"
            "  curl -fsSL https://claude.ai/install.sh | bash"
        )

    def _check_auth(self) -> None:
        """
        Check if user is authenticated.

        Raises:
            ClaudeCodeAuthError: If authentication is required
        """
        # Try a simple query to check auth
        try:
            # Use -p flag for prompt-only mode
            result = subprocess.run(
                [self.cli_path, "-p", "test"],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Check for auth errors in output
            if "login" in result.stderr.lower() or "authenticate" in result.stderr.lower():
                raise ClaudeCodeAuthError(
                    "Authentication required. Run:\n"
                    f"  {self.cli_path} /login"
                )

        except subprocess.TimeoutExpired:
            # Timeout is acceptable for auth check
            pass
        except FileNotFoundError:
            raise ClaudeCodeNotFoundError(f"CLI not found at {self.cli_path}")

    def query(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        output_format: Optional[str] = None
    ) -> str:
        """
        Execute a one-shot query to Claude Code.

        Args:
            prompt: The prompt/question to send
            timeout: Timeout in seconds (default: from config)
            working_dir: Working directory for command (default: current dir)
            model_name: Model to use (overrides config, e.g., "sonnet", "haiku", "opus")
            output_format: Output format - "text" (default), "json", or "stream-json"

        Returns:
            Claude's response as text (or JSON if output_format="json")

        Raises:
            ClaudeCodeCLIError: If command fails
            subprocess.TimeoutExpired: If command times out
        """
        timeout = timeout or self.config.timeout
        working_dir = working_dir or self.config.working_dir or os.getcwd()
        model = model_name or self.config.model_name

        try:
            # Build command with optional flags
            cmd = [self.cli_path]

            # Add model flag if specified
            # Claude Code uses --model with aliases: sonnet, haiku, opus
            if model:
                cmd.extend(["--model", model])

            # Add output format flag if specified (only works with -p/--print)
            # Options: "text" (default), "json", "stream-json"
            if output_format:
                cmd.extend(["--output-format", output_format])

            # Add prompt (using -p for print mode)
            cmd.extend(["-p", prompt])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir
            )

            if result.returncode != 0:
                error_msg = f"Claude Code CLI failed with code {result.returncode}"
                if result.stdout:
                    error_msg += f"\nstdout: {result.stdout}"
                if result.stderr:
                    error_msg += f"\nstderr: {result.stderr}"
                raise ClaudeCodeCLIError(error_msg)

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise ClaudeCodeCLIError(
                f"Query timed out after {timeout} seconds"
            )
        except FileNotFoundError:
            raise ClaudeCodeNotFoundError(
                f"Claude Code CLI not found at {self.cli_path}"
            )

