#!/bin/bash

# Help text to display when --help is provided
show_help() {
  echo "AI Hedge Fund Docker Runner"
  echo ""
  echo "Usage: ./run.sh [OPTIONS] COMMAND"
  echo ""
  echo "Options:"
  echo "  --ticker SYMBOLS    Comma-separated list of ticker symbols (e.g., AAPL,MSFT,NVDA)"
  echo "  --start-date DATE   Start date in YYYY-MM-DD format"
  echo "  --end-date DATE     End date in YYYY-MM-DD format"
  echo "  --initial-cash AMT  Initial cash position (default: 100000.0)"
  echo "  --margin-requirement RATIO  Margin requirement ratio (default: 0.0)"
  echo "  --ollama            Use Ollama for local LLM inference"
  echo "  --ollama-base-url URL  Use an existing Ollama endpoint (implies --ollama)"
  echo "  --show-reasoning    Show reasoning from each agent"
  echo ""
  echo "Commands:"
  echo "  main                Run the main hedge fund application"
  echo "  backtest            Run the backtester"
  echo "  build               Build the Docker image"
  echo "  compose             Run using Docker Compose with integrated Ollama"
  echo "  ollama              Start only the Ollama container for model management"
  echo "  pull MODEL          Pull a specific model into the Ollama container"
  echo "  help                Show this help message"
  echo ""
  echo "Examples:"
  echo "  ./run.sh --ticker AAPL,MSFT,NVDA main"
  echo "  ./run.sh --ticker AAPL,MSFT,NVDA --ollama main"
  echo "  ./run.sh --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 backtest"
  echo "  ./run.sh compose    # Run with Docker Compose (includes Ollama)"
  echo "  ./run.sh ollama     # Start only the Ollama container"
  echo "  ./run.sh pull llama3 # Pull the llama3 model to Ollama"
  echo ""
}

# Default values
TICKER="AAPL,MSFT,NVDA"
USE_OLLAMA=""
OLLAMA_BASE_URL_VALUE="${OLLAMA_BASE_URL:-}"
USE_EXTERNAL_OLLAMA=""
START_DATE=""
END_DATE=""
INITIAL_AMOUNT="100000.0"
MARGIN_REQUIREMENT="0.0"
SHOW_REASONING=""
COMMAND=""
MODEL_NAME=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --ticker)
      TICKER="$2"
      shift 2
      ;;
    --start-date)
      START_DATE="--start-date $2"
      shift 2
      ;;
    --end-date)
      END_DATE="--end-date $2"
      shift 2
      ;;
    --initial-cash)
      INITIAL_AMOUNT="$2"
      shift 2
      ;;
    --margin-requirement)
      MARGIN_REQUIREMENT="$2"
      shift 2
      ;;
    --ollama)
      USE_OLLAMA="--ollama"
      shift
      ;;
    --ollama-base-url)
      OLLAMA_BASE_URL_VALUE="$2"
      USE_EXTERNAL_OLLAMA="1"
      if [ -z "$USE_OLLAMA" ]; then
        USE_OLLAMA="--ollama"
      fi
      shift 2
      ;;
    --show-reasoning)
      SHOW_REASONING="--show-reasoning"
      shift
      ;;
    main|backtest|build|help|compose|ollama)
      COMMAND="$1"
      shift
      ;;
    pull)
      COMMAND="pull"
      MODEL_NAME="$2"
      shift 2
      ;;
    --help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

# Determine if we should use an external Ollama instance
if [ -n "$USE_OLLAMA" ] && [ -z "$USE_EXTERNAL_OLLAMA" ] && [ -n "$OLLAMA_BASE_URL_VALUE" ]; then
  if [ "$OLLAMA_BASE_URL_VALUE" != "http://ollama:11434" ] && [ "$OLLAMA_BASE_URL_VALUE" != "http://ollama:11434/" ]; then
    USE_EXTERNAL_OLLAMA="1"
  fi
fi

if [ "$USE_EXTERNAL_OLLAMA" = "1" ] && [ -z "$OLLAMA_BASE_URL_VALUE" ]; then
  echo "Error: --ollama-base-url requires a value."
  exit 1
fi

# Check if command is provided
if [ -z "$COMMAND" ]; then
  echo "Error: No command specified."
  show_help
  exit 1
fi

# Show help if 'help' command is provided
if [ "$COMMAND" = "help" ]; then
  show_help
  exit 0
fi

# Check for Docker Compose existence
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
  echo "Error: Docker Compose is not installed."
  exit 1
fi

# Determine which Docker Compose command to use
if command -v docker-compose &> /dev/null; then
  COMPOSE_CMD="docker-compose"
else
  COMPOSE_CMD="docker compose"
fi

# Detect system architecture for GPU configuration
ARCH=$(uname -m)
OS=$(uname -s)
GPU_CONFIG=""

# Set appropriate GPU configuration based on architecture
if [ "$OS" = "Darwin" ] && { [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; }; then
  echo "Detected Apple Silicon (M-series) - Metal GPU acceleration should be enabled"
  # Metal GPU is handled via environment variables in docker-compose.yml
elif command -v nvidia-smi &> /dev/null; then
  echo "NVIDIA GPU detected - Adding NVIDIA GPU configuration"
  GPU_CONFIG="-f docker-compose.yml -f docker-compose.nvidia.yml"
fi

# Build the Docker image if 'build' command is provided
if [ "$COMMAND" = "build" ]; then
  docker build -t ai-hedge-fund -f Dockerfile ..
  exit 0
fi

# Start Ollama container if 'ollama' command is provided
if [ "$COMMAND" = "ollama" ]; then
  echo "Starting Ollama container..."
  $COMPOSE_CMD $GPU_CONFIG --profile embedded-ollama up -d ollama
  
  # Check if Ollama is running
  echo "Waiting for Ollama to start..."
  for i in {1..30}; do
    if docker run --rm --network=host curlimages/curl:latest curl -s http://localhost:11434/api/version &> /dev/null; then
      echo "Ollama is now running."
      # Show available models
      echo "Available models:"
      docker exec -t ollama ollama list
      
      echo -e "\nManage your models using:"
      echo "  ./run.sh pull <model-name>   # Download a model"
      echo "  ./run.sh ollama              # Start Ollama and show models"
      exit 0
    fi
    echo -n "."
    sleep 1
  done
  
  echo "Failed to start Ollama within the expected time. You may need to check the container logs."
  exit 1
fi

# Pull a model if 'pull' command is provided
if [ "$COMMAND" = "pull" ]; then
  if [ -z "$MODEL_NAME" ]; then
    echo "Error: No model name specified."
    echo "Usage: ./run.sh pull <model-name>"
    echo "Example: ./run.sh pull llama3"
    exit 1
  fi
  
  # Start Ollama if it's not already running
  $COMPOSE_CMD $GPU_CONFIG --profile embedded-ollama up -d ollama
  
  # Wait for Ollama to start
  echo "Ensuring Ollama is running..."
  for i in {1..30}; do
    if docker run --rm --network=host curlimages/curl:latest curl -s http://localhost:11434/api/version &> /dev/null; then
      echo "Ollama is running."
      break
    fi
    echo -n "."
    sleep 1
  done
  
  # Pull the model
  echo "Pulling model: $MODEL_NAME"
  echo "This may take some time depending on the model size and your internet connection."
  echo "You can press Ctrl+C to cancel at any time (the model will continue downloading in the background)."
  
  docker exec -t ollama ollama pull "$MODEL_NAME"
  
  # Check if the model was successfully pulled
  if docker exec -t ollama ollama list | grep -q "$MODEL_NAME"; then
    echo "Model $MODEL_NAME was successfully downloaded."
  else
    echo "Warning: Model $MODEL_NAME may not have been properly downloaded."
    echo "Check the Ollama container status with: ./run.sh ollama"
  fi
  
  exit 0
fi

# Run with Docker Compose
if [ "$COMMAND" = "compose" ]; then
  echo "Running with Docker Compose (includes Ollama)..."
  $COMPOSE_CMD $GPU_CONFIG --profile embedded-ollama up --build
  exit 0
fi

# Check if .env file exists, if not create from .env.example
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "Please edit .env file to add your API keys."
  else
    echo "Error: No .env or .env.example file found."
    exit 1
  fi
fi

# Set script path and parameters based on command
if [ "$COMMAND" = "main" ]; then
  SCRIPT_PATH="src/main.py"
  if [ "$COMMAND" = "main" ]; then
    INITIAL_PARAM="--initial-cash $INITIAL_AMOUNT"
  fi
elif [ "$COMMAND" = "backtest" ]; then
  SCRIPT_PATH="src/backtester.py"
  if [ "$COMMAND" = "backtest" ]; then
    INITIAL_PARAM="--initial-capital $INITIAL_AMOUNT"
  fi
fi

# If using Ollama, prepare embedded service or external connection
if [ -n "$USE_OLLAMA" ]; then
  if [ -n "$OLLAMA_BASE_URL_VALUE" ]; then
    export OLLAMA_BASE_URL="$OLLAMA_BASE_URL_VALUE"
  fi

  COMMAND_OVERRIDE=""

  if [ -n "$START_DATE" ]; then
    COMMAND_OVERRIDE="$COMMAND_OVERRIDE $START_DATE"
  fi

  if [ -n "$END_DATE" ]; then
    COMMAND_OVERRIDE="$COMMAND_OVERRIDE $END_DATE"
  fi

  if [ -n "$INITIAL_PARAM" ]; then
    COMMAND_OVERRIDE="$COMMAND_OVERRIDE $INITIAL_PARAM"
  fi

  if [ -n "$MARGIN_REQUIREMENT" ]; then
    COMMAND_OVERRIDE="$COMMAND_OVERRIDE --margin-requirement $MARGIN_REQUIREMENT"
  fi

  if [ "$USE_EXTERNAL_OLLAMA" = "1" ]; then
    TRIMMED_BASE="${OLLAMA_BASE_URL_VALUE%/}"
    if [ -z "$TRIMMED_BASE" ]; then
      TRIMMED_BASE="${OLLAMA_BASE_URL%/}"
    fi
    if [ -z "$TRIMMED_BASE" ]; then
      echo "Error: No external Ollama base URL provided."
      exit 1
    fi
    HEALTHCHECK_URL="$TRIMMED_BASE/api/version"
    echo "Using external Ollama endpoint at $TRIMMED_BASE"
    echo "Checking connectivity to Ollama..."
    REACHABLE=false
    for i in {1..30}; do
      if docker run --rm --network=host curlimages/curl:latest curl -s "$HEALTHCHECK_URL" &> /dev/null; then
        REACHABLE=true
        break
      fi
      echo -n "."
      sleep 1
    done
    echo ""
    if [ "$REACHABLE" = false ]; then
      echo "Warning: Unable to reach Ollama at $HEALTHCHECK_URL within 30 seconds."
      echo "Continuing anyway; ensure the endpoint is reachable from within the containers."
    else
      echo "External Ollama endpoint is reachable."
    fi
  else
    echo "Setting up embedded Ollama container for local LLM inference..."
    $COMPOSE_CMD $GPU_CONFIG --profile embedded-ollama up -d ollama

    echo "Waiting for Ollama to start..."
    EMBEDDED_REACHABLE=false
    for i in {1..30}; do
      if docker run --rm --network=host curlimages/curl:latest curl -s http://localhost:11434/api/version &> /dev/null; then
        EMBEDDED_REACHABLE=true
        echo "Ollama is running."
        echo "Available models:"
        docker exec -t ollama ollama list
        break
      fi
      echo -n "."
      sleep 1
    done
    echo ""
    if [ "$EMBEDDED_REACHABLE" = false ]; then
      echo "Warning: Unable to confirm embedded Ollama startup within 30 seconds."
    fi
  fi

  if [[ "$(docker images -q ai-hedge-fund 2> /dev/null)" == "" ]]; then
    echo "Building AI Hedge Fund image..."
    docker build -t ai-hedge-fund -f Dockerfile ..
  fi

  echo "Running AI Hedge Fund with Ollama using Docker Compose..."

  if [ "$COMMAND" = "main" ]; then
    if [ -n "$SHOW_REASONING" ]; then
      $COMPOSE_CMD $GPU_CONFIG run --rm hedge-fund-reasoning python src/main.py --ticker $TICKER $COMMAND_OVERRIDE $SHOW_REASONING --ollama
    else
      $COMPOSE_CMD $GPU_CONFIG run --rm hedge-fund-ollama python src/main.py --ticker $TICKER $COMMAND_OVERRIDE --ollama
    fi
  elif [ "$COMMAND" = "backtest" ]; then
    $COMPOSE_CMD $GPU_CONFIG run --rm backtester-ollama python src/backtester.py --ticker $TICKER $COMMAND_OVERRIDE $SHOW_REASONING --ollama
  fi

  exit 0
fi
# Standard Docker run (without Ollama)
# Build the command
CMD="docker run -it --rm -v $(pwd)/.env:/app/.env"

# Add the command
CMD="$CMD ai-hedge-fund python $SCRIPT_PATH --ticker $TICKER $START_DATE $END_DATE $INITIAL_PARAM --margin-requirement $MARGIN_REQUIREMENT $SHOW_REASONING"

# Run the command
echo "Running: $CMD"
$CMD 