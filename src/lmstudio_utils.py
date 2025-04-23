#!/usr/bin/env python3
"""
Command line utilities for managing LM Studio models.
This script allows you to list models available in LM Studio server.
"""

import argparse
import sys
import os
from utils.lmstudio import (
    is_lmstudio_server_running,
    get_available_lmstudio_models,
    suggest_installing_lmstudio,
    format_model_names
)
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

def main():
    parser = argparse.ArgumentParser(description="LM Studio model management utility")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all available models in LM Studio")
    
    args = parser.parse_args()
    
    # Check if LM Studio server is running
    if not is_lmstudio_server_running():
        print(f"{Fore.RED}LM Studio server is not running.{Style.RESET_ALL}")
        suggest_installing_lmstudio()
        sys.exit(1)
    
    if args.command == "list" or not args.command:
        # List models from LM Studio API
        models = get_available_lmstudio_models()
        formatted_models = format_model_names(models)
        
        if not formatted_models:
            print(f"{Fore.YELLOW}No models found in LM Studio server.{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}Models available in LM Studio:{Style.RESET_ALL}")
            for model in formatted_models:
                print(f"  - {model['display_name']} ({model['model_name']})")
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 