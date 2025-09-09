# Web Application
The AI Hedge Fund app is a complete system with both frontend and backend components that enables you to run an AI-powered hedge fund trading system through a web interface on your own computer.

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />


## Overview

The AI Hedge Fund consists of:

- **Backend**: A FastAPI application that provides a REST API to run the hedge fund trading system and backtester
- **Frontend**: A React/Vite application that offers a user-friendly interface to visualize and control the hedge fund operations

## Table of Contents

- [🚀 Quick Start (For Non-Technical Users)](#-quick-start-for-non-technical-users)
  - [Option 1: Using 1-Line Shell Script (Recommended)](#option-1-using-1-line-shell-script-recommended)
  - [Option 2: Using npm (Alternative)](#option-2-using-npm-alternative)
- [🛠️ Manual Setup (For Developers)](#️-manual-setup-for-developers)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running the Application](#running-the-application)
- [Detailed Documentation](#detailed-documentation)
- [Disclaimer](#disclaimer)
- [Troubleshooting](#troubleshooting])

## 🚀 Quick Start (For Non-Technical Users)

**One-line setup and run command:**

### Option 1: Using 1-Line Shell Script (Recommended)

#### For Mac/Linux:
```bash
./run.sh
```

If you get a "permission denied" error, run this first:
```bash
chmod +x run.sh && ./run.sh
```

Or alternatively, you can run:
```bash
bash run.sh
```

#### For Windows:
```cmd
run.bat
```

### Option 2: Using npm (Alternative)
```bash
cd app && npm install && npm run setup
```

**That's it!** These scripts will:
1. Check for required dependencies (Node.js, Python, Poetry)
2. Install all dependencies automatically
3. Start both frontend and backend services
4. **Automatically open your web browser** to the application

**Requirements:**
- [Node.js](https://nodejs.org/) (includes npm)
- [Python 3](https://python.org/)
- [Poetry](https://python-poetry.org/)

**After running, you can access:**
- Frontend (Web Interface): http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

---

## 🛠️ Manual Setup (For Developers)

If you prefer to set up each component manually or need more control:

### Prerequisites

- Node.js and npm for the frontend
- Python 3.8+ and Poetry for the backend

### Installation

1. Clone the repository:
```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

2. Set up your environment variables:
```bash
# Create .env file for your API keys (in the root directory)
cp .env.example .env
```

3. Edit the .env file to add your API keys:
```bash
# For running LLMs hosted by openai (gpt-4o, gpt-4o-mini, etc.)
OPENAI_API_KEY=your-openai-api-key

# For running LLMs hosted by groq (deepseek, llama3, etc.)
GROQ_API_KEY=your-groq-api-key

# For getting financial data to power the hedge fund
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

4. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

5. Install project dependencies:

**Option A: Using pip (Recommended for Windows):**
```bash
# From the root directory - install all dependencies via requirements.txt
.venv/Scripts/python.exe -m pip install -r requirements.txt

# If some packages are missing, install individually:
.venv/Scripts/python.exe -m pip install fastapi==0.104.1 uvicorn[standard]==0.35.0
```

**Option B: Using Poetry (if available):**
```bash
# From the root directory
poetry install
```

7. Install frontend app dependencies:
```bash
cd app/frontend
npm install  # or pnpm install or yarn install
```

### Running the Application

1. Start the backend server:
```bash
# IMPORTANT: Run from project root directory (not app/backend)
# Option 1: Using virtual environment directly
.venv/Scripts/python.exe -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000

# Option 2: Using Poetry (if available)
poetry run uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000
```

2. Start the frontend application:
```bash
# In another terminal, from the frontend directory
cd app/frontend
npm run dev
```

You can now access:
- Frontend application: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Detailed Documentation

For more detailed information:
- [Backend Documentation](./backend/README.md)
- [Frontend Documentation](./frontend/README.md)

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No warranties or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions

By using this software, you agree to use it solely for learning purposes.

## Troubleshooting

### Common Issues

#### "No module named 'fastapi'" or "No module named 'uvicorn'" Error
If you see these import errors when starting the backend:

**Solution (Windows):**
```bash
# Install missing dependencies directly
.venv/Scripts/python.exe -m pip install fastapi==0.104.1
.venv/Scripts/python.exe -m pip install uvicorn[standard]==0.35.0
.venv/Scripts/python.exe -m pip install sqlalchemy==2.0.36
```

**Alternative - Reinstall all dependencies:**
```bash
# From project root
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

#### Backend Startup Issues
**Symptoms:** Backend fails to start or import errors
**Solutions:**
1. **Ensure you're in the correct directory:** Run backend command from project root, not `app/backend/`
2. **Check Python path:** Use `.venv/Scripts/python.exe` on Windows
3. **Verify dependencies:** Test with `.venv/Scripts/python.exe -c "import fastapi, uvicorn, sqlalchemy"`

#### Python Version Issues
- **Use Python 3.11**: Python 3.13+ may have compatibility issues
- **Check your Python version:** `python --version`
- **Switch Python versions if needed** (using pyenv, conda, etc.)

#### Environment Variable Issues
- **Ensure .env file exists** in the project root directory
- **Copy from template:** `cp .env.example .env`
- **Add your API keys** to the .env file

#### Permission Issues (Mac/Linux)
If you get "permission denied":
```bash
chmod +x run.sh
./run.sh
```

#### Port Already in Use
If ports 8000 or 5173 are in use:

**Windows:**
```bash
# Kill processes using ports
taskkill /f /im python.exe
taskkill /f /im node.exe

# Or find and kill specific port processes
netstat -ano | findstr :8000
netstat -ano | findstr :5173
# Then use: taskkill /f /pid [PID_NUMBER]
```

**Mac/Linux:**
```bash
# Kill existing processes
pkill -f "uvicorn\|vite"
# Or use different ports by modifying the scripts
```

#### Frontend npm Issues (Windows)
If you get permission errors during `npm install`:
```bash
# Clean npm cache
npm cache clean --force

# Delete node_modules and reinstall
cd app/frontend
rm -rf node_modules package-lock.json
npm install
```

### Getting Help
- Check the [GitHub Issues](https://github.com/virattt/ai-hedge-fund/issues)
- Follow updates on [Twitter](https://x.com/virattt) 
