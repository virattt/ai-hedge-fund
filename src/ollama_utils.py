#!/usr/bin/env python3
"""
Command line utilities for managing Ollama models.
This script allows you to delete and re-download Ollama models.
"""

import argparse
import sys
from utils.ollama import (
    is_ollama_installed,
    is_ollama_server_running,
    get_locally_available_models,
    start_ollama_server,
    download_model,
    delete_model
)
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

def main():
    parser = argparse.ArgumentParser(description="Ollama model management utility")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all downloaded models")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a model")
    delete_parser.add_argument("model", help="Model name to delete (e.g., gemma3:4b)")
    
    # Download command
    download_parser = subparsers.add_parser("download", help="Download a model")
    download_parser.add_argument("model", help="Model name to download (e.g., gemma3:4b)")
    
    # Reinstall command
    reinstall_parser = subparsers.add_parser("reinstall", help="Delete and re-download a model")
    reinstall_parser.add_argument("model", help="Model name to reinstall (e.g., gemma3:4b)")
    
    args = parser.parse_args()
    
    # Check if Ollama is installed
    if not is_ollama_installed():
        print(f"{Fore.RED}Ollama is not installed on your system.{Style.RESET_ALL}")
        sys.exit(1)
    
    # Start the server if needed
    if not is_ollama_server_running():
        print(f"{Fore.YELLOW}Starting Ollama server...{Style.RESET_ALL}")
        if not start_ollama_server():
            print(f"{Fore.RED}Failed to start Ollama server.{Style.RESET_ALL}")
            sys.exit(1)
    
    if args.command == "list":
        models = get_locally_available_models()
        if not models:
            print(f"{Fore.YELLOW}No models are currently downloaded.{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}Downloaded models:{Style.RESET_ALL}")
            for model in models:
                print(f"  - {model}")
                
    elif args.command == "delete":
        if delete_model(args.model):
            print(f"{Fore.GREEN}Successfully deleted model {args.model}.{Style.RESET_ALL}")
        else:
            sys.exit(1)
            
    elif args.command == "download":
        if download_model(args.model):
            print(f"{Fore.GREEN}Successfully downloaded model {args.model}.{Style.RESET_ALL}")
        else:
            sys.exit(1)
            
    elif args.command == "reinstall":
        print(f"{Fore.CYAN}Reinstalling model {args.model}...{Style.RESET_ALL}")
        
        # First delete the model
        if not delete_model(args.model):
            print(f"{Fore.RED}Failed to delete model {args.model}. Continuing with download anyway...{Style.RESET_ALL}")
        
        # Then download it again
        if download_model(args.model):
            print(f"{Fore.GREEN}Successfully reinstalled model {args.model}.{Style.RESET_ALL}")
        else:
            sys.exit(1)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 