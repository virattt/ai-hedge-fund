# CLAUDE.md - Docker Configuration

Docker setup for containerized execution of the AI hedge fund system.

## Architecture

### `docker-compose.yml`
Multi-service setup with:
- **ollama**: Local LLM server (Ollama) with GPU acceleration support
- **hedge-fund**: Main hedge fund execution 
- **hedge-fund-reasoning**: Hedge fund with detailed reasoning output
- **hedge-fund-ollama**: Hedge fund using local Ollama models
- **backtester**: Backtesting system
- **backtester-ollama**: Backtesting with local models

### `Dockerfile`
Python 3.11 slim container with:
- Poetry dependency management
- Virtual environment disabled for container efficiency
- PYTHONPATH configured for proper imports

## Service Configuration

### Ollama Service
- **Image**: `ollama/ollama:latest`
- **Port**: 11434 (exposed to host)
- **GPU**: Apple Silicon Metal acceleration enabled
- **Storage**: Persistent volume for model data
- **Networking**: Accessible to other services via `ollama:11434`

### Hedge Fund Services
All services share:
- Same base image built from root context
- Environment variable injection from `../.env`
- Dependency on Ollama service
- Interactive TTY for output visibility
- Unbuffered Python output for real-time logs

## Usage Commands

```bash
# Build all services
docker-compose build

# Run specific service
docker-compose up hedge-fund
docker-compose up backtester
docker-compose up hedge-fund-ollama

# Run with custom parameters (modify docker-compose.yml)
# Default: --ticker AAPL,MSFT,NVDA

# View logs
docker-compose logs hedge-fund
docker-compose logs -f ollama

# Clean up
docker-compose down
docker-compose down -v  # Remove volumes
```

## Shell Scripts

### `run.sh` (Linux/Mac)
Wrapper script for easy Docker execution:
- Builds images if needed  
- Passes through command line arguments
- Handles different execution modes (main, backtest)

### `run.bat` (Windows)
Windows equivalent of run.sh with same functionality

## Development Workflow

### Local Development
1. Build base image: `docker-compose build`
2. Start Ollama: `docker-compose up ollama -d`
3. Run hedge fund: `docker-compose up hedge-fund`

### Adding New Services
1. Define service in `docker-compose.yml`
2. Set appropriate command and environment variables
3. Add dependency on `ollama` if using local models
4. Mount `.env` file for configuration

### GPU Support
- **Apple Silicon**: Metal acceleration pre-configured
- **NVIDIA**: Add `runtime: nvidia` and GPU device mapping
- **CPU Only**: Remove GPU-related environment variables

## Environment Variables

Container environment:
- `PYTHONUNBUFFERED=1`: Real-time output
- `OLLAMA_BASE_URL=http://ollama:11434`: Local model access
- `PYTHONPATH=/app`: Import path configuration

Host environment (via `.env`):
- API keys for external LLM services
- Financial data API keys
- Model configuration preferences