@echo off
REM AI Hedge Fund Web Application Setup and Runner (Windows)
REM This script makes it easy for non-technical users to run the full web application

REM Colors for output
set "INFO=[INFO]"
set "SUCCESS=[SUCCESS]"
set "WARNING=[WARNING]"
set "ERROR=[ERROR]"

REM Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo %ERROR% Node.js is not installed. Please install from https://nodejs.org/
    pause
    exit /b 1
)

REM Check npm
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo %ERROR% npm is not installed. Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check Python (or python3)
where python >nul 2>&1
if %errorlevel% neq 0 (
    where python3 >nul 2>&1
    if %errorlevel% neq 0 (
        echo %ERROR% Python is not installed. Please install from https://python.org/
        pause
        exit /b 1
    )
)

REM Check Poetry
where poetry >nul 2>&1
if %errorlevel% neq 0 (
    REM Try alternative Poetry locations
    if exist "%APPDATA%\Python\Scripts\poetry.exe" (
        echo %INFO% Poetry found in user directory. Adding to PATH temporarily...
        set "PATH=%APPDATA%\Python\Scripts;%PATH%"
        goto :poetry_found
    )
    if exist "%APPDATA%\Python\Python311\Scripts\poetry.exe" (
        echo %INFO% Poetry found in Python311 user directory. Adding to PATH temporarily...
        set "PATH=%APPDATA%\Python\Python311\Scripts;%PATH%"
        goto :poetry_found
    )
    echo %WARNING% Poetry is not installed.
    echo %INFO% Poetry is required to manage Python dependencies for this project.
    echo.
    set /p install_poetry="Would you like to install Poetry automatically? (y/N): "
    if /i "%install_poetry%"=="y" (
        echo %INFO% Installing Poetry using official installer...
        
        REM Download the installer script first, then run it
        curl -sSL https://install.python-poetry.org -o "%TEMP%\install-poetry.py"
        if %errorlevel% neq 0 (
            echo %WARNING% Failed to download Poetry installer. Trying alternative method...
            python -m pip install --user poetry
            if %errorlevel% neq 0 (
                echo %ERROR% Failed to install Poetry automatically.
                echo %INFO% This is likely due to Windows permission restrictions or network issues.
                echo.
                echo %INFO% SOLUTION: Please try one of these options:
                echo %INFO% 1. Run this script as Administrator
                echo %INFO% 2. Manual install: curl -sSL https://install.python-poetry.org -o install-poetry.py
                echo %INFO% 3. Then run: python install-poetry.py
                echo.
                pause
                exit /b 1
            )
        ) else (
            REM Run the downloaded installer
            python "%TEMP%\install-poetry.py"
            if %errorlevel% neq 0 (
                echo %ERROR% Failed to install Poetry with official installer.
                echo %INFO% Trying alternative method with pip...
                python -m pip install --user poetry
                if %errorlevel% neq 0 (
                    echo %ERROR% Failed to install Poetry automatically.
                    echo %INFO% This is likely due to Windows permission restrictions or network issues.
                    echo.
                    echo %INFO% SOLUTION: Please try one of these options:
                    echo %INFO% 1. Run this script as Administrator
                    echo %INFO% 2. Manual install: curl -sSL https://install.python-poetry.org -o install-poetry.py
                    echo %INFO% 3. Then run: python install-poetry.py
                    echo.
                    pause
                    exit /b 1
                )
            )
            REM Clean up the temporary installer file
            del "%TEMP%\install-poetry.py" >nul 2>&1
        )
        echo %SUCCESS% Poetry installed successfully!
        echo %INFO% Refreshing environment...
        call refreshenv >nul 2>&1 || echo %WARNING% Could not refresh environment.
        
        REM Check if Poetry is now available
        where poetry >nul 2>&1
        if %errorlevel% neq 0 (
            echo %WARNING% Poetry was installed but is not yet available in PATH.
            echo %INFO% You may need to restart your terminal or add Poetry to your PATH.
            echo %INFO% Poetry is typically installed to: %APPDATA%\Python\Scripts
            echo %INFO% You can also try running the script again after restarting your terminal.
            pause
            exit /b 1
        )
        echo %SUCCESS% Poetry is now available and ready to use!
    ) else (
        echo %ERROR% Poetry is required to run this application.
        echo %ERROR% Please install Poetry manually using one of these methods:
        echo %INFO% 1. Download installer: curl -sSL https://install.python-poetry.org -o install-poetry.py
        echo %INFO% 2. Run installer: python install-poetry.py
        echo %INFO% 3. Restart your terminal and run this script again
        pause
        exit /b 1
    )
)

:poetry_found
echo %SUCCESS% Poetry is available!

REM Ensure correct working directory
if not exist "frontend" (
    echo %ERROR% This script must be run from the app\ directory
    echo %ERROR% Please navigate to the app\ directory and run: run.bat
    pause
    exit /b 1
)

if not exist "backend" (
    echo %ERROR% This script must be run from the app\ directory
    echo %ERROR% Please navigate to the app\ directory and run: run.bat
    pause
    exit /b 1
)

echo.
echo %INFO% AI Hedge Fund Web Application Setup
echo %INFO% This script will install dependencies and start both frontend and backend services
echo.

REM Check for .env
if not exist "..\.env" (
    if exist "..\.env.example" (
        echo %WARNING% No .env file found. Creating from .env.example...
        copy "..\.env.example" "..\.env"
        echo %WARNING% Please edit ..\.env to add your API keys:
        echo %WARNING%   - OPENAI_API_KEY=your-openai-api-key
        echo %WARNING%   - GROQ_API_KEY=your-groq-api-key
        echo %WARNING%   - FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
        echo.
    ) else (
        echo %ERROR% No .env or .env.example file found in the root directory.
        echo %ERROR% Please create a .env file with your API keys.
        pause
        exit /b 1
    )
) else (
    echo %SUCCESS% Environment file (.env)
)

REM Setup database
echo %INFO% Setting up database...
echo %INFO% Database: SQLite (hedge_fund.db)
echo %INFO% Location: Project root directory
echo %INFO% Tables will be created automatically on first backend startup

if exist "..\hedge_fund.db" (
    echo %SUCCESS% Database file already exists
) else (
    echo %INFO% Database will be created when backend starts for the first time
)

REM Install backend dependencies
echo %INFO% Installing backend dependencies...
cd backend

poetry run python -c "import uvicorn; import fastapi" >nul 2>&1
if %errorlevel% equ 0 (
    echo %SUCCESS% Backend dependencies already installed
) else (
    echo %INFO% Installing Python dependencies with Poetry...
    poetry install
    if %errorlevel% neq 0 (
        echo %ERROR% Failed to install backend dependencies
        pause
        exit /b 1
    ) else (
        echo %SUCCESS% Backend dependencies installed successfully
    )
)

cd ..

REM Install frontend dependencies
echo %INFO% Installing frontend dependencies...
cd frontend

if exist "node_modules" (
    echo %SUCCESS% Frontend dependencies already installed
) else (
    echo %INFO% Installing Node.js dependencies...
    npm install
    if %errorlevel% neq 0 (
        echo %ERROR% Failed to install frontend dependencies
        pause
        exit /b 1
    )
    echo %SUCCESS% Frontend dependencies installed
)

cd ..

REM Start services
echo %INFO% Starting the AI Hedge Fund web application...
echo %INFO% Press Ctrl+C to stop all services
echo.

REM Start backend
echo %INFO% Launching backend server...
REM Run from project root to ensure proper Python imports
cd ..
start /b poetry run uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000
cd app

timeout /t 3 /nobreak >nul

REM Check database initialization
echo %INFO% Checking database initialization...
timeout /t 2 /nobreak >nul

if exist "..\hedge_fund.db" (
    echo %SUCCESS% Database initialized successfully
) else (
    echo %WARNING% Database file not found, but will be created on first API call
)

REM Start frontend
echo %INFO% Launching frontend development server...
cd frontend
start /b npm run dev
cd ..

timeout /t 5 /nobreak >nul

echo %INFO% Opening browser...
timeout /t 2 /nobreak >nul
start http://localhost:5173

echo.
echo %SUCCESS% AI Hedge Fund web application is now running
echo %INFO% Frontend: http://localhost:5173
echo %INFO% Backend:  http://localhost:8000
echo %INFO% Docs:     http://localhost:8000/docs
echo %INFO% Database: SQLite (hedge_fund.db in project root)
echo.
echo %INFO% Press any key to stop both services...
pause >nul

REM Stop services
taskkill /f /im "uvicorn.exe" >nul 2>&1
taskkill /f /im "node.exe" >nul 2>&1

echo %SUCCESS% Services stopped. Goodbye
pause
