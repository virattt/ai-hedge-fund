#!/usr/bin/env python3
"""Debug script to check the parser arguments"""

import os
import sys
import subprocess

# Print the Python path
print("Python sys.path:", sys.path)
print("PYTHONPATH environment variable:", os.environ.get("PYTHONPATH"))

# Use a direct approach - run the python commands to see the full output
print("\n--- Running src.main with --help ---")
try:
    subprocess.run(["python", "-m", "src.main", "--help"], check=False)
except Exception as e:
    print(f"Error running src.main: {e}")

print("\n--- Checking available arguments in src/main.py ---")
try:
    # List the file to see its content
    print("Contents of src/main.py (first 20 lines):")
    with open("/app/src/main.py", "r") as f:
        for i, line in enumerate(f):
            if i < 20:
                print(f"{i+1}: {line.rstrip()}")
            else:
                break
except Exception as e:
    print(f"Error reading src/main.py: {e}")

# Run a direct Python command to check arguments
print("\n--- Direct Python check of main.py arguments ---")
try:
    cmd = """
import sys
sys.path.insert(0, '/app')
from src.main import parser
print("Arguments defined in parser:")
for action in parser._actions:
    print(f"- {action.dest}: {action.option_strings}")
"""
    subprocess.run(["python", "-c", cmd], check=False)
except Exception as e:
    print(f"Error checking main.py arguments: {e}")
