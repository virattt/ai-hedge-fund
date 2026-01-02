@echo off
setlocal enabledelayedexpansion

:: Default values
set TICKER=AAPL,MSFT,NVDA
set USE_OLLAMA=
set "OLLAMA_BASE_URL_VALUE=%OLLAMA_BASE_URL%"
set USE_EXTERNAL_OLLAMA=
set START_DATE=
set END_DATE=
set INITIAL_AMOUNT=100000.0
set MARGIN_REQUIREMENT=0.0
set SHOW_REASONING=
set COMMAND=
set MODEL_NAME=

:: Help function
:show_help
echo AI Hedge Fund Docker Runner
echo.
echo Usage: run.bat [OPTIONS] COMMAND
echo.
echo Options:
echo   --ticker SYMBOLS    Comma-separated list of ticker symbols (e.g., AAPL,MSFT,NVDA)
echo   --start-date DATE   Start date in YYYY-MM-DD format
echo   --end-date DATE     End date in YYYY-MM-DD format
echo   --initial-cash AMT  Initial cash position (default: 100000.0)
echo   --margin-requirement RATIO  Margin requirement ratio (default: 0.0)
echo   --ollama            Use Ollama for local LLM inference
echo   --ollama-base-url URL  Use an existing Ollama endpoint (implies --ollama)
echo   --show-reasoning    Show reasoning from each agent
echo.
echo Commands:
echo   main                Run the main hedge fund application
echo   backtest            Run the backtester
echo   build               Build the Docker image
echo   compose             Run using Docker Compose with integrated Ollama
echo   ollama              Start only the Ollama container for model management
echo   pull MODEL          Pull a specific model into the Ollama container
echo   help                Show this help message
echo.
echo Examples:
echo   run.bat --ticker AAPL,MSFT,NVDA main
echo   run.bat --ticker AAPL,MSFT,NVDA --ollama main
echo   run.bat --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 backtest
echo   run.bat compose     # Run with Docker Compose (includes Ollama)
echo   run.bat ollama      # Start only the Ollama container
echo   run.bat pull llama3 # Pull the llama3 model to Ollama
echo.
goto :eof

:: Parse arguments
:parse_args
if "%~1"=="" goto :check_command
if "%~1"=="--ticker" (
    set TICKER=%~2
    shift
    shift
    goto :parse_args
)
if "%~1"=="--start-date" (
    set START_DATE=--start-date %~2
    shift
    shift
    goto :parse_args
)
if "%~1"=="--end-date" (
    set END_DATE=--end-date %~2
    shift
    shift
    goto :parse_args
)
if "%~1"=="--initial-cash" (
    set INITIAL_AMOUNT=%~2
    shift
    shift
    goto :parse_args
)
if "%~1"=="--margin-requirement" (
    set MARGIN_REQUIREMENT=%~2
    shift
    shift
    goto :parse_args
)
if "%~1"=="--ollama" (
    set USE_OLLAMA=--ollama
    shift
    goto :parse_args
)
if "%~1"=="--ollama-base-url" (
    set "OLLAMA_BASE_URL_VALUE=%~2"
    set USE_EXTERNAL_OLLAMA=1
    if "!USE_OLLAMA!"=="" (
        set USE_OLLAMA=--ollama
    )
    shift
    shift
    goto :parse_args
)
if "%~1"=="--show-reasoning" (
    set SHOW_REASONING=--show-reasoning
    shift
    goto :parse_args
)
if "%~1"=="main" (
    set COMMAND=main
    shift
    goto :parse_args
)
if "%~1"=="backtest" (
    set COMMAND=backtest
    shift
    goto :parse_args
)
if "%~1"=="build" (
    set COMMAND=build
    shift
    goto :parse_args
)
if "%~1"=="compose" (
    set COMMAND=compose
    shift
    goto :parse_args
)
if "%~1"=="ollama" (
    set COMMAND=ollama
    shift
    goto :parse_args
)
if "%~1"=="pull" (
    set COMMAND=pull
    set MODEL_NAME=%~2
    shift
    shift
    goto :parse_args
)
if "%~1"=="help" (
    call :show_help
    exit /b 0
)
if "%~1"=="--help" (
    call :show_help
    exit /b 0
)
echo Unknown option: %~1
call :show_help
exit /b 1

:check_command
if defined USE_OLLAMA (
    if not defined USE_EXTERNAL_OLLAMA if not "!OLLAMA_BASE_URL_VALUE!"=="" (
        set "__OLLAMA_CHECK=!OLLAMA_BASE_URL_VALUE!"
        if /I not "!__OLLAMA_CHECK!"=="http://ollama:11434" if /I not "!__OLLAMA_CHECK!"=="http://ollama:11434/" (
            set USE_EXTERNAL_OLLAMA=1
        )
        set "__OLLAMA_CHECK="
    )
)

if defined USE_EXTERNAL_OLLAMA (
    if "!OLLAMA_BASE_URL_VALUE!"=="" (
        echo Error: --ollama-base-url requires a value.
        exit /b 1
    )
)

if "!COMMAND!"=="" (
    echo Error: No command specified.
    call :show_help
    exit /b 1
)

:: Show help if 'help' command is provided
if "!COMMAND!"=="help" (
    call :show_help
    exit /b 0
)

:: Check for Docker Compose existence
docker compose version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set COMPOSE_CMD=docker compose
) else (
    docker-compose --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set COMPOSE_CMD=docker-compose
    ) else (
        echo Error: Docker Compose is not installed.
        exit /b 1
    )
)

:: Build the Docker image if 'build' command is provided
if "!COMMAND!"=="build" (
    docker build -t ai-hedge-fund -f Dockerfile ..
    exit /b 0
)

:: Start Ollama container if 'ollama' command is provided
if "!COMMAND!"=="ollama" (
    echo Starting Ollama container...
    !COMPOSE_CMD! --profile embedded-ollama up -d ollama
    
    :: Check if Ollama is running
    echo Waiting for Ollama to start...
    for /l %%i in (1, 1, 30) do (
        !COMPOSE_CMD! exec ollama curl -s http://localhost:11434/api/version >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo Ollama is now running.
            :: Show available models
            echo Available models:
            !COMPOSE_CMD! exec ollama ollama list
            
            echo.
            echo Manage your models using:
            echo   run.bat pull ^<model-name^>   # Download a model
            echo   run.bat ollama              # Start Ollama and show models
            exit /b 0
        )
        timeout /t 1 /nobreak >nul
        echo.
    )
    
    echo Failed to start Ollama within the expected time. You may need to check the container logs.
    exit /b 1
)

:: Pull a model if 'pull' command is provided
if "!COMMAND!"=="pull" (
    if "!MODEL_NAME!"=="" (
        echo Error: No model name specified.
        echo Usage: run.bat pull ^<model-name^>
        echo Example: run.bat pull llama3
        exit /b 1
    )
    
    :: Start Ollama if it's not already running
    !COMPOSE_CMD! --profile embedded-ollama up -d ollama
    
    :: Wait for Ollama to start
    echo Ensuring Ollama is running...
    for /l %%i in (1, 1, 30) do (
        !COMPOSE_CMD! exec ollama curl -s http://localhost:11434/api/version >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            echo Ollama is running.
            goto :pull_model
        )
        timeout /t 1 /nobreak >nul
        echo.
    )
    
    :pull_model
    :: Pull the model
    echo Pulling model: !MODEL_NAME!
    echo This may take some time depending on the model size and your internet connection.
    echo You can press Ctrl+C to cancel at any time (the model will continue downloading in the background).
    
    !COMPOSE_CMD! exec ollama ollama pull "!MODEL_NAME!"
    
    :: Check if the model was successfully pulled
    !COMPOSE_CMD! exec ollama ollama list | findstr /i "!MODEL_NAME!" >nul
    if !ERRORLEVEL! EQU 0 (
        echo Model !MODEL_NAME! was successfully downloaded.
    ) else (
        echo Warning: Model !MODEL_NAME! may not have been properly downloaded.
        echo Check the Ollama container status with: run.bat ollama
    )
    
    exit /b 0
)

:: Run with Docker Compose if 'compose' command is provided
if "!COMMAND!"=="compose" (
    echo Running with Docker Compose (includes Ollama)...
    !COMPOSE_CMD! --profile embedded-ollama up --build
    exit /b 0
)

:: Check if .env file exists, if not create from .env.example
if not exist .env (
    if exist .env.example (
        echo No .env file found. Creating from .env.example...
        copy .env.example .env
        echo Please edit .env file to add your API keys.
    ) else (
        echo Error: No .env or .env.example file found.
        exit /b 1
    )
)

:: Set script path and parameters based on command
if "!COMMAND!"=="main" (
    set SCRIPT_PATH=src/main.py
    if "!COMMAND!"=="main" (
        set INITIAL_PARAM=--initial-cash !INITIAL_AMOUNT!
    )
) else if "!COMMAND!"=="backtest" (
    set SCRIPT_PATH=src/backtester.py
    if "!COMMAND!"=="backtest" (
        set INITIAL_PARAM=--initial-capital !INITIAL_AMOUNT!
    )
)

:: If using Ollama, prepare embedded service or external connection
if not "!USE_OLLAMA!"=="" (
    if not "!OLLAMA_BASE_URL_VALUE!"=="" (
        set "OLLAMA_BASE_URL=!OLLAMA_BASE_URL_VALUE!"
    )

    set COMMAND_OVERRIDE=

    if not "!START_DATE!"=="" (
        set COMMAND_OVERRIDE=!COMMAND_OVERRIDE! !START_DATE!
    )

    if not "!END_DATE!"=="" (
        set COMMAND_OVERRIDE=!COMMAND_OVERRIDE! !END_DATE!
    )

    if not "!INITIAL_PARAM!"=="" (
        set COMMAND_OVERRIDE=!COMMAND_OVERRIDE! !INITIAL_PARAM!
    )

    if not "!MARGIN_REQUIREMENT!"=="" (
        set COMMAND_OVERRIDE=!COMMAND_OVERRIDE! --margin-requirement !MARGIN_REQUIREMENT!
    )

    if defined USE_EXTERNAL_OLLAMA (
        set "TRIMMED_BASE=!OLLAMA_BASE_URL_VALUE!"
        if "!TRIMMED_BASE!"=="" set "TRIMMED_BASE=!OLLAMA_BASE_URL!"
        if "!TRIMMED_BASE!"=="" (
            echo Error: No external Ollama base URL provided.
            exit /b 1
        )
        if "!TRIMMED_BASE:~-1!"=="/" set "TRIMMED_BASE=!TRIMMED_BASE:~0,-1!"
        set "HEALTHCHECK_URL=!TRIMMED_BASE!/api/version"
        echo Using external Ollama endpoint at !TRIMMED_BASE!
        echo Checking connectivity to Ollama...
        set REACHABLE=
        for /l %%i in (1, 1, 30) do (
            powershell -NoLogo -Command "try {Invoke-WebRequest -Uri '!HEALTHCHECK_URL!' -UseBasicParsing -TimeoutSec 2 ^| Out-Null; exit 0} catch { exit 1 }" >nul 2>&1
            if !ERRORLEVEL! EQU 0 (
                set REACHABLE=1
                goto :external_check_done
            )
            timeout /t 1 /nobreak >nul
            echo.
        )
:external_check_done
        if defined REACHABLE (
            echo External Ollama endpoint is reachable.
        ) else (
            echo Warning: Unable to reach Ollama at !HEALTHCHECK_URL! within 30 seconds.
            echo Continuing anyway; ensure the endpoint is reachable from within the containers.
        )
    ) else (
        echo Setting up embedded Ollama container for local LLM inference...
        !COMPOSE_CMD! --profile embedded-ollama up -d ollama

        echo Waiting for Ollama to start...
        for /l %%i in (1, 1, 30) do (
            !COMPOSE_CMD! exec ollama curl -s http://localhost:11434/api/version >nul 2>&1
            if !ERRORLEVEL! EQU 0 (
                echo Ollama is running.
                echo Available models:
                !COMPOSE_CMD! exec ollama ollama list
                goto :continue_ollama
            )
            timeout /t 1 /nobreak >nul
            echo.
        )
        echo Warning: Unable to confirm Ollama startup within 30 seconds.
:continue_ollama
    )

    docker images -q ai-hedge-fund 2>nul | findstr /r /c:"^..*$" >nul
    if !ERRORLEVEL! NEQ 0 (
        echo Building AI Hedge Fund image...
        docker build -t ai-hedge-fund -f Dockerfile ..
    )

    echo Running AI Hedge Fund with Ollama using Docker Compose...

    if "!COMMAND!"=="main" (
        if not "!SHOW_REASONING!"=="" (
            !COMPOSE_CMD! run --rm hedge-fund-reasoning python src/main.py --ticker !TICKER! !COMMAND_OVERRIDE! !SHOW_REASONING! --ollama
        ) else (
            !COMPOSE_CMD! run --rm hedge-fund-ollama python src/main.py --ticker !TICKER! !COMMAND_OVERRIDE! --ollama
        )
    ) else if "!COMMAND!"=="backtest" (
        !COMPOSE_CMD! run --rm backtester-ollama python src/backtester.py --ticker !TICKER! !COMMAND_OVERRIDE! !SHOW_REASONING! --ollama
    )

    exit /b 0
)

:: Standard Docker run (without Ollama)
:: Build the command
set CMD=docker run -it --rm -v %cd%\.env:/app/.env

:: Add the command
set CMD=!CMD! ai-hedge-fund python !SCRIPT_PATH! --ticker !TICKER! !START_DATE! !END_DATE! !INITIAL_PARAM! --margin-requirement !MARGIN_REQUIREMENT! !SHOW_REASONING!

:: Run the command
echo Running: !CMD!
!CMD!

:: Exit
exit /b 0

:: Start script execution
call :parse_args %* 

