#!/usr/bin/env python3
# test_imports.py - A simple script to verify that Python imports are working correctly

import sys
print("Python path:", sys.path)

try:
    from src.utils.display import print_trading_output
    print("Successfully imported from src.utils.display")
except ImportError as e:
    print(f"Error importing src.utils.display: {e}")

try:
    from src.agents.portfolio_manager import portfolio_management_agent
    print("Successfully imported from src.agents.portfolio_manager")
except ImportError as e:
    print(f"Error importing src.agents.portfolio_manager: {e}")

print("Import test complete.")
