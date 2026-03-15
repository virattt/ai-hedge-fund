"""Utilities for working with MLX LM server (Apple Silicon).

mlx-lm runs large language models natively on Apple Silicon (M1/M2/M3/M4)
using Apple's MLX framework and exposes an OpenAI-compatible HTTP server.

LAN usage
---------
Start the server on your Mac with:
    mlx_lm.server --model mlx-community/Llama-3.1-8B-Instruct-4bit \\
                  --host 0.0.0.0 --port 8080

Point other machines on the same network at it by setting in their .env:
    MLX_BASE_URL=http://<mac-ip>:8080/v1

Install
-------
    pip install mlx-lm          # Apple Silicon only
    # or inside the project:
    poetry add mlx-lm

Requirements: macOS + Apple Silicon (M1/M2/M3/M4).
"""

import os
import platform
import subprocess
import time

import requests
from colorama import Fore, Style

DEFAULT_MLX_PORT = 8080
DEFAULT_MLX_HOST = "localhost"
DEFAULT_MLX_BASE_URL = f"http://{DEFAULT_MLX_HOST}:{DEFAULT_MLX_PORT}/v1"

# Background server process (started by this module)
_server_process: subprocess.Popen | None = None


# ---------------------------------------------------------------------------
# URL / auth helpers
# ---------------------------------------------------------------------------
def _get_mlx_base_url() -> str:
    """Return the configured MLX base URL (no trailing slash)."""
    host = os.environ.get("MLX_HOST", DEFAULT_MLX_HOST)
    default = f"http://{host}:{DEFAULT_MLX_PORT}/v1"
    return os.environ.get("MLX_BASE_URL", default).rstrip("/")


def _get_mlx_api_key() -> str | None:
    """Return the MLX API key if set, else None."""
    return os.environ.get("MLX_API_KEY") or None


def _auth_headers() -> dict:
    """Return Authorization header dict when an API key is configured."""
    key = _get_mlx_api_key()
    return {"Authorization": f"Bearer {key}"} if key else {}


def is_apple_silicon() -> bool:
    """Return True when running on Apple Silicon."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


# ---------------------------------------------------------------------------
# Install / runtime checks
# ---------------------------------------------------------------------------
def is_mlx_lm_installed() -> bool:
    """Return True if the mlx_lm Python package is importable."""
    try:
        import importlib.util
        return importlib.util.find_spec("mlx_lm") is not None
    except Exception:
        return False


def is_mlx_server_running() -> bool:
    """Return True if an MLX LM server is reachable at the configured URL.

    Sends the configured API key so secured servers (that return 401 for
    unauthenticated requests) are still recognised as running.
    """
    url = _get_mlx_base_url()
    headers = _auth_headers()
    for path in ("/models", "/health"):
        try:
            response = requests.get(f"{url}{path}", headers=headers, timeout=2)
            # 200 = up, 401 = up but wrong/missing key (handle separately),
            # 404 = up but endpoint absent — all mean the server is reachable.
            if response.status_code in (200, 401, 404):
                return True
        except requests.RequestException:
            pass
    return False


def get_locally_available_models() -> list[str]:
    """Return model IDs reported by the running MLX server's /v1/models endpoint."""
    if not is_mlx_server_running():
        return []
    try:
        url = _get_mlx_base_url()
        response = requests.get(f"{url}/models", headers=_auth_headers(), timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [m["id"] for m in data.get("data", [])]
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------
def start_mlx_server(model_name: str, host: str = "0.0.0.0", port: int | None = None) -> bool:
    """Start `mlx_lm.server` as a background subprocess.

    The server binds to *host* (default ``0.0.0.0``) so it is reachable from
    other devices on the LAN.  Pass ``host="localhost"`` to restrict to the
    local machine only.

    Returns True when the server becomes reachable within 30 seconds.
    """
    global _server_process

    if is_mlx_server_running():
        print(f"{Fore.GREEN}MLX server is already running.{Style.RESET_ALL}")
        return True

    if not is_mlx_lm_installed():
        print(f"{Fore.RED}mlx-lm is not installed.  Run: pip install mlx-lm{Style.RESET_ALL}")
        return False

    if not is_apple_silicon():
        print(f"{Fore.RED}MLX requires Apple Silicon (M1/M2/M3/M4).  "
              f"Set MLX_BASE_URL to point at a remote MLX server instead.{Style.RESET_ALL}")
        return False

    port = port or DEFAULT_MLX_PORT
    cmd = [
        "python", "-m", "mlx_lm.server",
        "--model", model_name,
        "--host", host,
        "--port", str(port),
    ]

    print(f"{Fore.YELLOW}Starting MLX server with model {model_name} …{Style.RESET_ALL}")
    print(f"{Fore.CYAN}This may take a minute while the model loads into memory.{Style.RESET_ALL}")

    try:
        _server_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print(f"{Fore.RED}Could not launch mlx_lm.server.  "
              f"Make sure mlx-lm is installed in the active Python environment.{Style.RESET_ALL}")
        return False

    # Wait up to 30 s for the server to start
    for _ in range(30):
        if is_mlx_server_running():
            print(f"{Fore.GREEN}MLX server started successfully "
                  f"(http://{host}:{port}/v1).{Style.RESET_ALL}")
            return True
        time.sleep(1)

    print(f"{Fore.RED}MLX server did not become reachable within 30 s.{Style.RESET_ALL}")
    return False


def stop_mlx_server() -> bool:
    """Terminate the MLX server process started by this module."""
    global _server_process
    if _server_process is None:
        return False
    try:
        _server_process.terminate()
        _server_process.wait(timeout=10)
        _server_process = None
        print(f"{Fore.GREEN}MLX server stopped.{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"{Fore.RED}Error stopping MLX server: {e}{Style.RESET_ALL}")
        return False


# ---------------------------------------------------------------------------
# High-level ensure helper (mirrors ollama.ensure_ollama_and_model)
# ---------------------------------------------------------------------------
def ensure_mlx_and_model(model_name: str) -> bool:
    """Ensure the MLX server is reachable and serving *model_name*.

    Workflow:
    1. If MLX_BASE_URL points to a remote host, just verify connectivity.
    2. Otherwise check for Apple Silicon + mlx-lm install, then start the
       server locally with the requested model.
    """
    base_url = _get_mlx_base_url()
    is_remote = not (
        base_url.startswith(f"http://localhost:{DEFAULT_MLX_PORT}")
        or base_url.startswith(f"http://127.0.0.1:{DEFAULT_MLX_PORT}")
    )

    if is_remote:
        # Remote MLX server — just check connectivity
        if is_mlx_server_running():
            print(f"{Fore.GREEN}Remote MLX server reachable at {base_url}.{Style.RESET_ALL}")
            return True
        print(f"{Fore.RED}Cannot reach remote MLX server at {base_url}.  "
              f"Make sure the server is running on that machine.{Style.RESET_ALL}")
        return False

    # Local server path
    if not is_apple_silicon():
        print(f"{Fore.RED}MLX requires Apple Silicon.  "
              f"Use MLX_BASE_URL to point at a remote MLX server.{Style.RESET_ALL}")
        return False

    if not is_mlx_lm_installed():
        print(f"{Fore.YELLOW}mlx-lm is not installed.{Style.RESET_ALL}")
        print(f"Install it with:  {Fore.CYAN}pip install mlx-lm{Style.RESET_ALL}")
        return False

    if is_mlx_server_running():
        print(f"{Fore.GREEN}MLX server is already running.{Style.RESET_ALL}")
        return True

    return start_mlx_server(model_name)
