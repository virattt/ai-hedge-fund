# Backend Server Troubleshooting Guide

This guide helps you resolve common issues when starting the AI Hedge Fund backend server.

## Quick Start Checklist

✅ **Prerequisites Met:**
- [ ] Python 3.11+ installed
- [ ] Poetry installed
- [ ] Dependencies installed (`poetry install`)
- [ ] Environment variables configured (`.env` file)

✅ **Basic Test:**
```bash
# Test if backend imports work
poetry run python -c "from app.backend.main import app; print('Backend imports successful')"
```

✅ **Start Server:**
```bash
# Option 1: Using the startup script (recommended)
python3 start_backend.py

# Option 2: Direct uvicorn command
poetry run uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload

# Option 3: Using the web app runner
cd app && ./run.sh
```

## Common Issues and Solutions

### 1. ModuleNotFoundError: No module named 'fastapi'

**Problem:** Dependencies not installed or Poetry environment not activated.

**Solution:**
```bash
# Install dependencies
poetry install

# Verify installation
poetry run python -c "import fastapi; print('FastAPI installed')"
```

### 2. NameError: name 'PositionType' is not defined

**Problem:** Class definition order issue in `src/data/models.py`.

**Solution:** This should be fixed in the current version. If you see this error:
```bash
# Check if you have the latest models.py
grep -n "class PositionType" src/data/models.py
# Should show only one definition around line 144
```

### 3. Import Error: Cannot import name 'SecurityInfo'

**Problem:** Forward reference issue or class ordering.

**Solution:** Ensure you have the latest version of `src/data/models.py` with proper forward references using strings:
```python
security_info: Optional["SecurityInfo"] = None
```

### 4. Database Connection Errors

**Problem:** SQLite database issues or permissions.

**Solution:**
```bash
# Check database file permissions
ls -la hedge_fund.db

# If corrupted, remove and recreate
rm hedge_fund.db
poetry run python -c "from app.backend.database.models import Base; from app.backend.database.connection import engine; Base.metadata.create_all(bind=engine)"
```

### 5. Port Already in Use

**Problem:** Port 8000 is occupied by another process.

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process (replace PID with actual process ID)
kill -9 <PID>

# Or use a different port
poetry run uvicorn app.backend.main:app --port 8001
```

### 6. Environment Variable Issues

**Problem:** Missing or incorrect API keys.

**Solution:**
```bash
# Check if .env file exists
ls -la .env

# Create .env from template if missing
cp .env.example .env

# Edit .env file to add your API keys
nano .env  # or your preferred editor
```

Required environment variables:
- At least one LLM API key: `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY`
- Optional: `FINANCIAL_DATASETS_API_KEY` (free data available for major stocks)

### 7. Poetry Command Not Found

**Problem:** Poetry not installed or not in PATH.

**Solution:**
```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"

# Reload shell
source ~/.bashrc  # or source ~/.zshrc

# Alternative: Install via pip
python3 -m pip install poetry
```

### 8. Python Version Compatibility

**Problem:** Python version too old.

**Solution:**
```bash
# Check Python version
python3 --version

# Should be 3.11 or higher
# If not, install newer Python:
# - macOS: brew install python@3.11
# - Ubuntu: sudo apt install python3.11
# - Windows: Download from python.org
```

### 9. Import Path Issues

**Problem:** Python can't find the modules.

**Solution:**
```bash
# Ensure you're running from the project root
pwd  # Should show /path/to/ai-hedge-fund

# Check Python path
poetry run python -c "import sys; print('\n'.join(sys.path))"

# Run with proper module path
poetry run python -m app.backend.main
```

### 10. CORS Issues

**Problem:** Frontend can't connect to backend.

**Solution:** Check CORS configuration in `app/backend/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Debugging Steps

### 1. Enable Verbose Logging

Add to your startup command:
```bash
poetry run uvicorn app.backend.main:app --log-level debug
```

### 2. Test Individual Components

```bash
# Test data models
poetry run python -c "from src.data.models import Position, Portfolio; print('Models OK')"

# Test database connection
poetry run python -c "from app.backend.database.connection import engine; print('Database OK')"

# Test routes
poetry run python -c "from app.backend.routes import api_router; print('Routes OK')"
```

### 3. Check Dependencies

```bash
# List installed packages
poetry show

# Check for conflicts
poetry check

# Update dependencies
poetry update
```

### 4. Fresh Installation

If all else fails, try a clean installation:
```bash
# Remove virtual environment
poetry env remove python

# Clean install
poetry install

# Verify installation
poetry run python -c "from app.backend.main import app; print('Success')"
```

## Performance Tips

### 1. Database Optimization

```bash
# Use a proper database for production
# In .env file:
DATABASE_URL=postgresql://user:password@localhost/hedge_fund
```

### 2. Production Settings

```bash
# Production startup
poetry run uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. Memory Usage

```bash
# Monitor memory usage
poetry run python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.1f} MB')
"
```

## Getting Help

If you're still having issues:

1. **Check the logs:** Look in `backend.log` for detailed error messages
2. **Run diagnostics:** Use the `start_backend.py` script for comprehensive checks
3. **Create an issue:** Include error logs and system information
4. **Community support:** Check existing issues and discussions

## System Information for Bug Reports

When reporting issues, include this information:
```bash
echo "System Information:"
echo "OS: $(uname -a)"
echo "Python: $(python3 --version)"
echo "Poetry: $(poetry --version)"
echo "Project directory: $(pwd)"
echo "Environment variables:"
env | grep -E "(OPENAI|GROQ|ANTHROPIC|DEEPSEEK|FINANCIAL)" | sed 's/=.*/=***/'
```

---

**Last Updated:** December 2024
**Version:** Compatible with AI Hedge Fund v0.1.0