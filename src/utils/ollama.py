"""Utilities for working with Ollama models"""

import logging
import os
import platform
import subprocess
import time
from typing import List

import questionary
import requests
from . import docker

logger = logging.getLogger(__name__)

# Constants
DEFAULT_OLLAMA_SERVER_URL = "http://localhost:11434"


def _get_ollama_base_url() -> str:
    """Return the configured Ollama base URL, trimming any trailing slash."""
    url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_SERVER_URL)
    if not url:
        url = DEFAULT_OLLAMA_SERVER_URL
    return url.rstrip("/")


def _get_ollama_endpoint(path: str) -> str:
    """Build a full Ollama API endpoint from the configured base URL."""
    base = _get_ollama_base_url()
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


OLLAMA_DOWNLOAD_URL = {"darwin": "https://ollama.com/download/darwin", "windows": "https://ollama.com/download/windows", "linux": "https://ollama.com/download/linux"}  # macOS  # Windows  # Linux
INSTALLATION_INSTRUCTIONS = {"darwin": "curl -fsSL https://ollama.com/install.sh | sh", "windows": "# Download from https://ollama.com/download/windows and run the installer", "linux": "curl -fsSL https://ollama.com/install.sh | sh"}


def is_ollama_installed() -> bool:
    """Check if Ollama is installed on the system."""
    system = platform.system().lower()

    if system == "darwin" or system == "linux":  # macOS or Linux
        try:
            result = subprocess.run(["which", "ollama"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.returncode == 0
        except Exception:
            return False
    elif system == "windows":  # Windows
        try:
            result = subprocess.run(["where", "ollama"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.returncode == 0
        except Exception:
            return False
    else:
        return False  # Unsupported OS


def is_ollama_server_running() -> bool:
    """Check if the Ollama server is running."""
    endpoint = _get_ollama_endpoint("/api/tags")
    try:
        response = requests.get(endpoint, timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_locally_available_models() -> List[str]:
    """Get a list of models that are already downloaded locally."""
    if not is_ollama_server_running():
        return []

    try:
        endpoint = _get_ollama_endpoint("/api/tags")
        response = requests.get(endpoint, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [model["name"] for model in data["models"]] if "models" in data else []
        return []
    except requests.RequestException:
        return []


def start_ollama_server() -> bool:
    """Start the Ollama server if it's not already running."""
    if is_ollama_server_running():
        logger.info("Ollama server is already running.")
        return True

    system = platform.system().lower()

    try:
        if system == "darwin" or system == "linux":  # macOS or Linux
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "windows":  # Windows
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            logger.error("Unsupported operating system: %s", system)
            return False

        # Wait for server to start
        for _ in range(10):  # Try for 10 seconds
            if is_ollama_server_running():
                logger.info("Ollama server started successfully.")
                return True
            time.sleep(1)

        logger.error("Failed to start Ollama server. Timed out waiting for server to become available.")
        return False
    except Exception as e:
        logger.error("Error starting Ollama server: %s", e)
        return False


def install_ollama() -> bool:
    """Install Ollama on the system."""
    system = platform.system().lower()
    if system not in OLLAMA_DOWNLOAD_URL:
        logger.error("Unsupported operating system for automatic installation: %s", system)
        logger.info("Please visit https://ollama.com/download to install Ollama manually.")
        return False

    if system == "darwin":  # macOS
        logger.info("Ollama for Mac is available as an application download.")

        # Default to offering the app download first for macOS users
        if questionary.confirm("Would you like to download the Ollama application?", default=True).ask():
            try:
                import webbrowser

                webbrowser.open(OLLAMA_DOWNLOAD_URL["darwin"])
                logger.info("Please download and install the application, then restart this program.")
                logger.info("After installation, you may need to open the Ollama app once before continuing.")

                # Ask if they want to try continuing after installation
                if questionary.confirm("Have you installed the Ollama app and opened it at least once?", default=False).ask():
                    # Check if it's now installed
                    if is_ollama_installed() and start_ollama_server():
                        logger.info("Ollama is now properly installed and running!")
                        return True
                    else:
                        logger.error("Ollama installation not detected. Please restart this application after installing Ollama.")
                        return False
                return False
            except Exception as e:
                logger.error("Failed to open browser: %s", e)
                return False
        else:
            # Only offer command-line installation as a fallback for advanced users
            if questionary.confirm("Would you like to try the command-line installation instead? (For advanced users)", default=False).ask():
                logger.info("Attempting command-line installation...")
                try:
                    install_process = subprocess.run(["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                    if install_process.returncode == 0:
                        logger.info("Ollama installed successfully via command line.")
                        return True
                    else:
                        logger.error("Command-line installation failed. Please use the app download method instead.")
                        return False
                except Exception as e:
                    logger.error("Error during command-line installation: %s", e)
                    return False
            return False
    elif system == "linux":  # Linux
        logger.info("Installing Ollama...")
        try:
            # Run the installation command as a single command
            install_process = subprocess.run(["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if install_process.returncode == 0:
                logger.info("Ollama installed successfully.")
                return True
            else:
                logger.error("Failed to install Ollama. Error: %s", install_process.stderr)
                return False
        except Exception as e:
            logger.error("Error during Ollama installation: %s", e)
            return False
    elif system == "windows":  # Windows
        logger.warning("Automatic installation on Windows is not supported.")
        logger.info("Please download and install Ollama from: %s", OLLAMA_DOWNLOAD_URL['windows'])

        # Ask if they want to open the download page
        if questionary.confirm("Do you want to open the Ollama download page in your browser?").ask():
            try:
                import webbrowser

                webbrowser.open(OLLAMA_DOWNLOAD_URL["windows"])
                logger.info("After installation, please restart this application.")

                # Ask if they want to try continuing after installation
                if questionary.confirm("Have you installed Ollama?", default=False).ask():
                    # Check if it's now installed
                    if is_ollama_installed() and start_ollama_server():
                        logger.info("Ollama is now properly installed and running!")
                        return True
                    else:
                        logger.error("Ollama installation not detected. Please restart this application after installing Ollama.")
                        return False
            except Exception as e:
                logger.error("Failed to open browser: %s", e)
        return False

    return False


def download_model(model_name: str) -> bool:
    """Download an Ollama model."""
    if not is_ollama_server_running():
        if not start_ollama_server():
            return False

    logger.info("Downloading model %s...", model_name)
    logger.info("This may take a while depending on your internet speed and the model size.")
    logger.info("The download is happening in the background. Please be patient...")

    try:
        # Use the Ollama CLI to download the model
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout to capture all output
            text=True,
            bufsize=1,  # Line buffered
            encoding='utf-8',  # Explicitly use UTF-8 encoding
            errors='replace'   # Replace any characters that cannot be decoded
        )
        
        # For tracking progress
        last_percentage = 0
        last_phase = ""

        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                output = output.strip()
                # Try to extract percentage information using a more lenient approach
                percentage = None
                current_phase = None

                # Example patterns in Ollama output:
                # "downloading: 23.45 MB / 42.19 MB [================>-------------] 55.59%"
                # "downloading model: 76%"
                # "pulling manifest: 100%"

                # Check for percentage in the output
                import re

                percentage_match = re.search(r"(\d+(\.\d+)?)%", output)
                if percentage_match:
                    try:
                        percentage = float(percentage_match.group(1))
                    except ValueError:
                        percentage = None

                # Try to determine the current phase (downloading, extracting, etc.)
                phase_match = re.search(r"^([a-zA-Z\s]+):", output)
                if phase_match:
                    current_phase = phase_match.group(1).strip()

                # If we found a percentage, display a progress bar
                if percentage is not None:
                    # Only update if there's a significant change (avoid flickering)
                    if abs(percentage - last_percentage) >= 1 or (current_phase and current_phase != last_phase):
                        last_percentage = percentage
                        if current_phase:
                            last_phase = current_phase

                        logger.info(
                            "Ollama download progress: model=%s, phase=%s, progress=%.1f%%",
                            model_name,
                            last_phase or "unknown",
                            percentage,
                        )
                else:
                    # If we couldn't extract a percentage but have identifiable output
                    if "download" in output.lower() or "extract" in output.lower() or "pulling" in output.lower():
                        logger.info("Ollama download status: model=%s, message=%s", model_name, output)

        # Wait for the process to finish
        return_code = process.wait()

        if return_code == 0:
            logger.info("Model %s downloaded successfully!", model_name)
            return True
        else:
            logger.error("Failed to download model %s. Check your internet connection and try again.", model_name)
            return False
    except Exception as e:
        logger.error("Error downloading model %s: %s", model_name, e)
        return False


def ensure_ollama_and_model(model_name: str) -> bool:
    """Ensure Ollama is installed, running, and the requested model is available."""
    ollama_url = _get_ollama_base_url()
    env_override = os.environ.get("OLLAMA_BASE_URL")

    # If an explicit base URL is provided (including Docker defaults), use the remote workflow
    if env_override or ollama_url.startswith("http://ollama:") or ollama_url.startswith("http://host.docker.internal:"):
        return docker.ensure_ollama_and_model(model_name, ollama_url)

    # Regular flow for environments that rely on the local Ollama install
    # Check if Ollama is installed
    if not is_ollama_installed():
        logger.warning("Ollama is not installed on your system.")
        
        # Ask if they want to install it
        if questionary.confirm("Do you want to install Ollama?").ask():
            if not install_ollama():
                return False
        else:
            logger.error("Ollama is required to use local models.")
            return False
    
    # Make sure the server is running
    if not is_ollama_server_running():
        logger.info("Starting Ollama server...")
        if not start_ollama_server():
            return False
    
    # Check if the model is already downloaded
    available_models = get_locally_available_models()
    if model_name not in available_models:
        logger.warning("Model %s is not available locally.", model_name)
        
        # Ask if they want to download it
        model_size_info = ""
        if "70b" in model_name:
            model_size_info = " This is a large model (up to several GB) and may take a while to download."
        elif "34b" in model_name or "8x7b" in model_name:
            model_size_info = " This is a medium-sized model (1-2 GB) and may take a few minutes to download."
        
        if questionary.confirm(f"Do you want to download the {model_name} model?{model_size_info} The download will happen in the background.").ask():
            return download_model(model_name)
        else:
            logger.error("The model is required to proceed.")
            return False
    
    return True


def delete_model(model_name: str) -> bool:
    """Delete a locally downloaded Ollama model."""
    # Check if we're running in Docker
    in_docker = os.environ.get("OLLAMA_BASE_URL", "").startswith("http://ollama:") or os.environ.get("OLLAMA_BASE_URL", "").startswith("http://host.docker.internal:")
    
    # In Docker environment, delegate to docker module
    if in_docker:
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        return docker.delete_model(model_name, ollama_url)
        
    # Non-Docker environment
    if not is_ollama_server_running():
        if not start_ollama_server():
            return False
    
    logger.info("Deleting model %s...", model_name)
    
    try:
        # Use the Ollama CLI to delete the model
        process = subprocess.run(["ollama", "rm", model_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if process.returncode == 0:
            logger.info("Model %s deleted successfully.", model_name)
            return True
        else:
            logger.error("Failed to delete model %s. Error: %s", model_name, process.stderr)
            return False
    except Exception as e:
        logger.error("Error deleting model %s: %s", model_name, e)
        return False


# Add this at the end of the file for command-line usage
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Ollama model manager")
    parser.add_argument("--check-model", help="Check if model exists and download if needed")
    args = parser.parse_args()

    if args.check_model:
        logger.info("Ensuring Ollama is installed and model %s is available", args.check_model)
        result = ensure_ollama_and_model(args.check_model)
        sys.exit(0 if result else 1)
    else:
        logger.info("No action specified. Use --check-model to check if a model exists.")
        sys.exit(1)
