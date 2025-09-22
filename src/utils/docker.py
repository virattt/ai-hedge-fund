"""Utilities for working with Ollama models in Docker environments"""

import requests
import time
from colorama import Fore, Style
import questionary

def ensure_ollama_and_model(model_name: str, ollama_url: str) -> bool:
    """Ensure the Ollama model is available at the target Ollama endpoint."""
    print(f"{Fore.CYAN}Using Ollama endpoint at {ollama_url}{Style.RESET_ALL}")
    
    # Step 1: Check if Ollama service is available
    if not is_ollama_available(ollama_url):
        return False
        
    # Step 2: Check if model is already available
    available_models = get_available_models(ollama_url)
    if model_name in available_models:
        print(f"{Fore.GREEN}Model {model_name} is available in the Docker Ollama container.{Style.RESET_ALL}")
        return True
        
    # Step 3: Model not available - ask if user wants to download
    print(f"{Fore.YELLOW}Model {model_name} is not available in the Docker Ollama container.{Style.RESET_ALL}")
    
    if not questionary.confirm(f"Do you want to download {model_name}?").ask():
        print(f"{Fore.RED}Cannot proceed without the model.{Style.RESET_ALL}")
        return False
        
    # Step 4: Download the model
    return download_model(model_name, ollama_url)


def is_ollama_available(ollama_url: str) -> bool:
    """Check if Ollama service is available in Docker environment."""
    try:
        response = requests.get(f"{ollama_url}/api/version", timeout=5)
        if response.status_code == 200:
            return True
            
        print(f"{Fore.RED}Cannot connect to Ollama service at {ollama_url}.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Make sure the Ollama service is running in your Docker environment.{Style.RESET_ALL}")
        return False
    except requests.RequestException as e:
        print(f"{Fore.RED}Error connecting to Ollama service: {e}{Style.RESET_ALL}")
        return False


def get_available_models(ollama_url: str) -> list:
    """Get list of available models in Docker environment."""
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return [m["name"] for m in models]
            
        print(f"{Fore.RED}Failed to get available models from Ollama service. Status code: {response.status_code}{Style.RESET_ALL}")
        return []
    except requests.RequestException as e:
        print(f"{Fore.RED}Error getting available models: {e}{Style.RESET_ALL}")
        return []


def download_model(model_name: str, ollama_url: str) -> bool:
    """Download a model in Docker environment."""
    print(f"{Fore.YELLOW}Downloading model {model_name} to the Docker Ollama container...{Style.RESET_ALL}")
    print(f"{Fore.CYAN}This may take some time. Please be patient.{Style.RESET_ALL}")
    
    # Step 1: Initiate the download
    try:
        response = requests.post(f"{ollama_url}/api/pull", json={"name": model_name}, timeout=10)
        if response.status_code != 200:
            print(f"{Fore.RED}Failed to initiate model download. Status code: {response.status_code}{Style.RESET_ALL}")
            if response.text:
                print(f"{Fore.RED}Error: {response.text}{Style.RESET_ALL}")
            return False
    except requests.RequestException as e:
        print(f"{Fore.RED}Error initiating download request: {e}{Style.RESET_ALL}")
        return False
    
    # Step 2: Monitor the download progress
    print(f"{Fore.CYAN}Download initiated. Checking periodically for completion...{Style.RESET_ALL}")
    
    total_wait_time = 0
    max_wait_time = 1800  # 30 minutes max wait
    check_interval = 10  # Check every 10 seconds
    
    while total_wait_time < max_wait_time:
        # Check if the model has been downloaded
        available_models = get_available_models(ollama_url)
        if model_name in available_models:
            print(f"{Fore.GREEN}Model {model_name} downloaded successfully.{Style.RESET_ALL}")
            return True
            
        # Wait before checking again
        time.sleep(check_interval)
        total_wait_time += check_interval
        
        # Print a status message every minute
        if total_wait_time % 60 == 0:
            minutes = total_wait_time // 60
            print(f"{Fore.CYAN}Download in progress... ({minutes} minute{'s' if minutes != 1 else ''} elapsed){Style.RESET_ALL}")
    
    # If we get here, we've timed out
    print(f"{Fore.RED}Timed out waiting for model download to complete after {max_wait_time // 60} minutes.{Style.RESET_ALL}")
    return False


def delete_model(model_name: str, ollama_url: str) -> bool:
    """Delete a model in Docker environment."""
    print(f"{Fore.YELLOW}Deleting model {model_name} from Docker container...{Style.RESET_ALL}")
    
    try:
        response = requests.delete(f"{ollama_url}/api/delete", json={"name": model_name}, timeout=10)
        if response.status_code == 200:
            print(f"{Fore.GREEN}Model {model_name} deleted successfully.{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}Failed to delete model. Status code: {response.status_code}{Style.RESET_ALL}")
            if response.text:
                print(f"{Fore.RED}Error: {response.text}{Style.RESET_ALL}")
            return False
    except requests.RequestException as e:
        print(f"{Fore.RED}Error deleting model: {e}{Style.RESET_ALL}")
        return False 