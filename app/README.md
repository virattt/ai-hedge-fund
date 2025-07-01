# AI Hedge Fund [WIP] 🚧

This project is currently a work in progress. To track progress, please get updates [here](https://x.com/virattt).

The AI Hedge Fund app is a complete system with both frontend and backend components that enables you to run an AI-powered hedge fund trading system through a web interface on your own computer.

<img width="1692" alt="Screenshot 2025-05-15 at 8 57 56 PM" src="https://github.com/user-attachments/assets/2173fa5b-1029-49dd-8b04-d7583616de1b" />


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

5. Install root project dependencies:
```bash
# From the root directory
poetry install
```

6. Install backend app dependencies:
```bash
# Navigate to the backend directory
cd app/backend
pip install -r requirements.txt  # If there's a requirements.txt file
# OR
poetry install  # If there's a pyproject.toml in the backend directory
```

7. Install frontend app dependencies:
```bash
cd app/frontend
npm install  # or pnpm install or yarn install
```

### Running the Application

1. Start the backend server:
```bash
# In one terminal, from the backend directory
cd app/backend
poetry run uvicorn main:app --reload
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
