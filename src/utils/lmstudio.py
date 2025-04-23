"""Utilities for working with LM Studio models"""

import platform
import subprocess
import requests
import time
import json
import os
from typing import List, Optional
import questionary
from colorama import Fore, Style

# Constants
LMSTUDIO_SERVER_URL = "http://localhost:1234"
LMSTUDIO_MODELS_ENDPOINT = f"{LMSTUDIO_SERVER_URL}/v1/models"
LMSTUDIO_DOWNLOAD_URL = {
    "darwin": "https://lmstudio.ai/download-mac",     # macOS
    "windows": "https://lmstudio.ai/download-win",     # Windows
    "linux": "https://lmstudio.ai/download-linux"     # Linux
}


def is_lmstudio_server_running() -> bool:
    """Check if the LM Studio server is running."""
    try:
        response = requests.get(LMSTUDIO_MODELS_ENDPOINT, timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_available_lmstudio_models() -> List[dict]:
    """Get a list of models that are available in LM Studio."""
    if not is_lmstudio_server_running():
        return []
    
    try:
        response = requests.get(LMSTUDIO_MODELS_ENDPOINT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        return []
    except requests.RequestException:
        return []


def format_model_names(models: List[dict]) -> List[dict]:
    """Format model information for display in UI."""
    formatted_models = []
    for model in models:
        model_id = model.get('id', '')
        model_name = os.path.basename(model_id) if os.path.sep in model_id else model_id
        # 计算模型的显示名称，通常是文件名
        display_name = f"[lmstudio] {model_name}"
        formatted_models.append({
            'display_name': display_name,
            'model_name': model_id,
            'provider': 'LM Studio'
        })
    return formatted_models


def suggest_installing_lmstudio() -> bool:
    """Suggest installing LM Studio if it's not running."""
    system = platform.system().lower()
    download_url = LMSTUDIO_DOWNLOAD_URL.get(system, LMSTUDIO_DOWNLOAD_URL['windows'])
    
    print(f"{Fore.YELLOW}LM Studio server is not running.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}You need to install and run LM Studio to use local models.{Style.RESET_ALL}")
    
    if questionary.confirm("Do you want to open the LM Studio download page in your browser?").ask():
        try:
            import webbrowser
            webbrowser.open(download_url)
            print(f"{Fore.YELLOW}After installation, please start LM Studio and enable the server.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}1. Open LM Studio{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}2. Go to Settings (gear icon){Style.RESET_ALL}")
            print(f"{Fore.YELLOW}3. Navigate to the 'Local Inference Server' tab{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}4. Enable 'OpenAI Compatible Server'{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}5. Click 'Start Server'{Style.RESET_ALL}")
            
            time.sleep(2)
            
            # Ask if they've started the server
            if questionary.confirm("Have you started the LM Studio server? (OpenAI Compatible Server)", default=False).ask():
                # Check if server is running
                if is_lmstudio_server_running():
                    print(f"{Fore.GREEN}LM Studio server is now running!{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}LM Studio server not detected. Please start the server in LM Studio.{Style.RESET_ALL}")
                    return False
        except Exception as e:
            print(f"{Fore.RED}Failed to open browser: {e}{Style.RESET_ALL}")
    
    return False


def ensure_lmstudio_server() -> bool:
    """Ensure LM Studio server is running."""
    if is_lmstudio_server_running():
        return True
    
    return suggest_installing_lmstudio() 