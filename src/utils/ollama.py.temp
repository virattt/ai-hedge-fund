"""Utilities for working with Ollama models"""

import platform
import subprocess
import requests
import time
from typing import List
import questionary
from colorama import Fore, Style

# Constants
OLLAMA_SERVER_URL = "http://localhost:11434"
OLLAMA_API_MODELS_ENDPOINT = f"{OLLAMA_SERVER_URL}/api/tags"
OLLAMA_DOWNLOAD_URL = {
    "darwin": "https://ollama.com/download/darwin",     # macOS
    "win32": "https://ollama.com/download/windows",     # Windows
    "linux": "https://ollama.com/download/linux"        # Linux
}
INSTALLATION_INSTRUCTIONS = {
    "darwin": "curl -fsSL https://ollama.com/install.sh | sh",
    "win32": "# Download from https://ollama.com/download/windows and run the installer",
    "linux": "curl -fsSL https://ollama.com/install.sh | sh"
}


def is_ollama_installed() -> bool:
    """Check if Ollama is installed on the system."""
    system = platform.system().lower()
    
    if system == "darwin" or system == "linux":  # macOS or Linux
        try:
            result = subprocess.run(["which", "ollama"], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True)
            return result.returncode == 0
        except Exception:
            return False
    elif system == "win32":  # Windows
        try:
            result = subprocess.run(["where", "ollama"], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True,
                                   shell=True)
            return result.returncode == 0
        except Exception:
            return False
    else:
        return False  # Unsupported OS


def is_ollama_server_running() -> bool:
    """Check if the Ollama server is running."""
    try:
        response = requests.get(OLLAMA_API_MODELS_ENDPOINT, timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_locally_available_models() -> List[str]:
    """Get a list of models that are already downloaded locally."""
    if not is_ollama_server_running():
        return []
    
    try:
        response = requests.get(OLLAMA_API_MODELS_ENDPOINT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [model['name'] for model in data['models']] if 'models' in data else []
        return []
    except requests.RequestException:
        return []


def start_ollama_server() -> bool:
    """Start the Ollama server if it's not already running."""
    if is_ollama_server_running():
        print(f"{Fore.GREEN}Ollama server is already running.{Style.RESET_ALL}")
        return True
    
    system = platform.system().lower()
    
    try:
        if system == "darwin" or system == "linux":  # macOS or Linux
            subprocess.Popen(["ollama", "serve"], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE)
        elif system == "windows":  # Windows
            subprocess.Popen(["ollama", "serve"], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE,
                           shell=True)
        else:
            print(f"{Fore.RED}Unsupported operating system: {system}{Style.RESET_ALL}")
            return False
        
        # Wait for server to start
        for _ in range(10):  # Try for 10 seconds
            if is_ollama_server_running():
                print(f"{Fore.GREEN}Ollama server started successfully.{Style.RESET_ALL}")
                return True
            time.sleep(1)
        
        print(f"{Fore.RED}Failed to start Ollama server. Timed out waiting for server to become available.{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"{Fore.RED}Error starting Ollama server: {e}{Style.RESET_ALL}")
        return False


def install_ollama() -> bool:
    """Install Ollama on the system."""
    system = platform.system().lower()
    if system not in OLLAMA_DOWNLOAD_URL:
        print(f"{Fore.RED}Unsupported operating system for automatic installation: {system}{Style.RESET_ALL}")
        print(f"Please visit https://ollama.com/download to install Ollama manually.")
        return False
    
    if system == "darwin":  # macOS
        print(f"{Fore.YELLOW}Ollama for Mac is available as an application download.{Style.RESET_ALL}")
        
        # Default to offering the app download first for macOS users
        if questionary.confirm("Would you like to download the Ollama application?", default=True).ask():
            try:
                import webbrowser
                webbrowser.open(OLLAMA_DOWNLOAD_URL["darwin"])
                print(f"{Fore.YELLOW}Please download and install the application, then restart this program.{Style.RESET_ALL}")
                print(f"{Fore.CYAN}After installation, you may need to open the Ollama app once before continuing.{Style.RESET_ALL}")
                
                # Ask if they want to try continuing after installation
                if questionary.confirm("Have you installed the Ollama app and opened it at least once?", default=False).ask():
                    # Check if it's now installed
                    if is_ollama_installed() and start_ollama_server():
                        print(f"{Fore.GREEN}Ollama is now properly installed and running!{Style.RESET_ALL}")
                        return True
                    else:
                        print(f"{Fore.RED}Ollama installation not detected. Please restart this application after installing Ollama.{Style.RESET_ALL}")
                        return False
                return False
            except Exception as e:
                print(f"{Fore.RED}Failed to open browser: {e}{Style.RESET_ALL}")
                return False
        else:
            # Only offer command-line installation as a fallback for advanced users
            if questionary.confirm("Would you like to try the command-line installation instead? (For advanced users)", default=False).ask():
                print(f"{Fore.YELLOW}Attempting command-line installation...{Style.RESET_ALL}")
                try:
                    install_process = subprocess.run(
                        ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        text=True
                    )
                    
                    if install_process.returncode == 0:
                        print(f"{Fore.GREEN}Ollama installed successfully via command line.{Style.RESET_ALL}")
                        return True
                    else:
                        print(f"{Fore.RED}Command-line installation failed. Please use the app download method instead.{Style.RESET_ALL}")
                        return False
                except Exception as e:
                    print(f"{Fore.RED}Error during command-line installation: {e}{Style.RESET_ALL}")
                    return False
            return False
    elif system == "linux":  # Linux
        print(f"{Fore.YELLOW}Installing Ollama...{Style.RESET_ALL}")
        try:
            # Run the installation command as a single command
            install_process = subprocess.run(
                ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            if install_process.returncode == 0:
                print(f"{Fore.GREEN}Ollama installed successfully.{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}Failed to install Ollama. Error: {install_process.stderr}{Style.RESET_ALL}")
                return False
        except Exception as e:
            print(f"{Fore.RED}Error during Ollama installation: {e}{Style.RESET_ALL}")
            return False
    elif system == "win32":  # Windows
        print(f"{Fore.YELLOW}Automatic installation on Windows is not supported.{Style.RESET_ALL}")
        print(f"Please download and install Ollama from: {OLLAMA_DOWNLOAD_URL['win32']}")
        
        # Ask if they want to open the download page
        if questionary.confirm("Do you want to open the Ollama download page in your browser?").ask():
            try:
                import webbrowser
                webbrowser.open(OLLAMA_DOWNLOAD_URL['win32'])
                print(f"{Fore.YELLOW}After installation, please restart this application.{Style.RESET_ALL}")
                
                # Ask if they want to try continuing after installation
                if questionary.confirm("Have you installed Ollama?", default=False).ask():
                    # Check if it's now installed
                    if is_ollama_installed() and start_ollama_server():
                        print(f"{Fore.GREEN}Ollama is now properly installed and running!{Style.RESET_ALL}")
                        return True
                    else:
                        print(f"{Fore.RED}Ollama installation not detected. Please restart this application after installing Ollama.{Style.RESET_ALL}")
                        return False
            except Exception as e:
                print(f"{Fore.RED}Failed to open browser: {e}{Style.RESET_ALL}")
        return False
    
    return False


def download_model(model_name: str) -> bool:
    """Download an Ollama model."""
    if not is_ollama_server_running():
        if not start_ollama_server():
            return False
    
    print(f"{Fore.YELLOW}Downloading model {model_name}...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}This may take a while depending on your internet speed and the model size.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}The download is happening in the background. Please be patient...{Style.RESET_ALL}")
    
    try:
        # Use the Ollama CLI to download the model
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout to capture all output
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
        
        # Show some progress to the user
        print(f"{Fore.CYAN}Download progress:{Style.RESET_ALL}")
        
        # For tracking progress
        last_percentage = 0
        last_phase = ""
        bar_length = 40
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
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
                percentage_match = re.search(r'(\d+(\.\d+)?)%', output)
                if percentage_match:
                    try:
                        percentage = float(percentage_match.group(1))
                    except ValueError:
                        percentage = None
                
                # Try to determine the current phase (downloading, extracting, etc.)
                phase_match = re.search(r'^([a-zA-Z\s]+):', output)
                if phase_match:
                    current_phase = phase_match.group(1).strip()
                
                # If we found a percentage, display a progress bar
                if percentage is not None:
                    # Only update if there's a significant change (avoid flickering)
                    if abs(percentage - last_percentage) >= 1 or (current_phase and current_phase != last_phase):
                        last_percentage = percentage
                        if current_phase:
                            last_phase = current_phase
                        
                        # Create a progress bar
                        filled_length = int(bar_length * percentage / 100)
                        bar = '█' * filled_length + '░' * (bar_length - filled_length)
                        
                        # Build the status line with the phase if available
                        phase_display = f"{Fore.CYAN}{last_phase.capitalize()}{Style.RESET_ALL}: " if last_phase else ""
                        status_line = f"\r{phase_display}{Fore.GREEN}{bar}{Style.RESET_ALL} {Fore.YELLOW}{percentage:.1f}%{Style.RESET_ALL}"
                        
                        # Print the status line without a newline to update in place
                        print(status_line, end='', flush=True)
                else:
                    # If we couldn't extract a percentage but have identifiable output
                    if "download" in output.lower() or "extract" in output.lower() or "pulling" in output.lower():
                        # Don't print a newline for percentage updates
                        if "%" in output:
                            print(f"\r{Fore.GREEN}{output}{Style.RESET_ALL}", end='', flush=True)
                        else:
                            print(f"{Fore.GREEN}{output}{Style.RESET_ALL}")
        
        # Wait for the process to finish
        return_code = process.wait()
        
        # Ensure we print a newline after the progress bar
        print()
        
        if return_code == 0:
            print(f"{Fore.GREEN}Model {model_name} downloaded successfully!{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}Failed to download model {model_name}. Check your internet connection and try again.{Style.RESET_ALL}")
            return False
    except Exception as e:
        print(f"\n{Fore.RED}Error downloading model {model_name}: {e}{Style.RESET_ALL}")
        return False


def ensure_ollama_and_model(model_name: str) -> bool:
    """Ensure Ollama is installed, running, and the requested model is available."""
    # Check if Ollama is installed
    if not is_ollama_installed():
        print(f"{Fore.YELLOW}Ollama is not installed on your system.{Style.RESET_ALL}")
        
        # Ask if they want to install it
        if questionary.confirm("Do you want to install Ollama?").ask():
            if not install_ollama():
                return False
        else:
            print(f"{Fore.RED}Ollama is required to use local models.{Style.RESET_ALL}")
            return False
    
    # Make sure the server is running
    if not is_ollama_server_running():
        print(f"{Fore.YELLOW}Starting Ollama server...{Style.RESET_ALL}")
        if not start_ollama_server():
            return False
    
    # Check if the model is already downloaded
    available_models = get_locally_available_models()
    if model_name not in available_models:
        print(f"{Fore.YELLOW}Model {model_name} is not available locally.{Style.RESET_ALL}")
        
        # Ask if they want to download it
        model_size_info = ""
        if "70b" in model_name:
            model_size_info = " This is a large model (up to several GB) and may take a while to download."
        elif "34b" in model_name or "8x7b" in model_name:
            model_size_info = " This is a medium-sized model (1-2 GB) and may take a few minutes to download."
        
        if questionary.confirm(f"Do you want to download the {model_name} model?{model_size_info} The download will happen in the background.").ask():
            return download_model(model_name)
        else:
            print(f"{Fore.RED}The model is required to proceed.{Style.RESET_ALL}")
            return False
    
    return True 


def delete_model(model_name: str) -> bool:
    """Delete a locally downloaded Ollama model."""
    if not is_ollama_server_running():
        if not start_ollama_server():
            return False
    
    print(f"{Fore.YELLOW}Deleting model {model_name}...{Style.RESET_ALL}")
    
    try:
        # Use the Ollama CLI to delete the model
        process = subprocess.run(
            ["ollama", "rm", model_name],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        if process.returncode == 0:
            print(f"{Fore.GREEN}Model {model_name} deleted successfully.{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}Failed to delete model {model_name}. Error: {process.stderr}{Style.RESET_ALL}")
            return False
    except Exception as e:
        print(f"{Fore.RED}Error deleting model {model_name}: {e}{Style.RESET_ALL}")
        return False 