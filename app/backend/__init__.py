import sys
from pathlib import Path

# Add the src directory to Python path for imports
# This is a temporary solution while we develop the backend
src_path = str(Path(__file__).parent.parent.parent / "src")
if src_path not in sys.path:
    sys.path.append(src_path)
