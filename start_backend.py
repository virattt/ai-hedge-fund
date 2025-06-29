#!/usr/bin/env python3
"""
Backend startup script with proper error handling and logging.
Ensures all dependencies are available and the server starts successfully.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backend.log')
    ]
)

logger = logging.getLogger(__name__)

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 11):
        logger.error(f"Python 3.11+ required, got {sys.version}")
        return False
    logger.info(f"Python version: {sys.version}")
    return True

def check_poetry():
    """Check if Poetry is installed and available"""
    try:
        result = subprocess.run(['poetry', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Poetry found: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    logger.error("Poetry not found. Please install Poetry: https://python-poetry.org/docs/#installation")
    return False

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        result = subprocess.run(['poetry', 'run', 'python', '-c', 'import fastapi, sqlalchemy, pydantic'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("All required dependencies are installed")
            return True
        else:
            logger.error(f"Dependency check failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error checking dependencies: {e}")
        return False

def install_dependencies():
    """Install dependencies using Poetry"""
    logger.info("Installing dependencies...")
    try:
        result = subprocess.run(['poetry', 'install'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Dependencies installed successfully")
            return True
        else:
            logger.error(f"Failed to install dependencies: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error installing dependencies: {e}")
        return False

def check_environment():
    """Check if required environment variables are set"""
    env_file = Path('.env')
    if not env_file.exists():
        logger.warning(".env file not found. Creating template...")
        create_env_template()
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check for at least one LLM API key
        llm_keys = ['OPENAI_API_KEY', 'GROQ_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY']
        has_llm_key = any(os.getenv(key) for key in llm_keys)
        
        if not has_llm_key:
            logger.warning("No LLM API key found. Some features may not work.")
            logger.info("Add at least one of these to your .env file:")
            for key in llm_keys:
                logger.info(f"  {key}=your_api_key_here")
        
        return True
    except ImportError:
        logger.warning("python-dotenv not installed. Environment variables won't be loaded automatically.")
        return True

def create_env_template():
    """Create a template .env file"""
    template = """# AI Hedge Fund Environment Variables
# Add your API keys here

# LLM API Keys (at least one required)
OPENAI_API_KEY=your_openai_api_key_here
GROQ_API_KEY=your_groq_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Financial Data API Key (optional - free data available for AAPL, GOOGL, MSFT, NVDA, TSLA)
FINANCIAL_DATASETS_API_KEY=your_financial_datasets_api_key_here

# Database URL (optional - uses SQLite by default)
DATABASE_URL=sqlite:///hedge_fund.db

# Other API Keys for enhanced features
NEWSAPI_KEY=your_newsapi_key_here
FRED_API_KEY=your_fred_api_key_here
"""
    
    with open('.env', 'w') as f:
        f.write(template)
    
    logger.info("Created .env template file. Please add your API keys.")

def test_imports():
    """Test that all critical imports work"""
    logger.info("Testing critical imports...")
    try:
        # Test app imports
        result = subprocess.run([
            'poetry', 'run', 'python', '-c', 
            'from app.backend.main import app; print("Backend imports successful")'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("All imports successful")
            return True
        else:
            logger.error(f"Import test failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error testing imports: {e}")
        return False

def start_server(host="0.0.0.0", port=8000, reload=True):
    """Start the FastAPI server using uvicorn"""
    logger.info(f"Starting backend server on http://{host}:{port}")
    
    cmd = [
        'poetry', 'run', 'uvicorn', 'app.backend.main:app',
        '--host', host,
        '--port', str(port)
    ]
    
    if reload:
        cmd.append('--reload')
    
    try:
        # Start the server
        subprocess.run(cmd)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        return False
    
    return True

def main():
    """Main startup routine"""
    logger.info("Starting AI Hedge Fund Backend Server...")
    
    # Pre-flight checks
    if not check_python_version():
        sys.exit(1)
    
    if not check_poetry():
        sys.exit(1)
    
    # Check and install dependencies
    if not check_dependencies():
        logger.info("Dependencies missing, attempting to install...")
        if not install_dependencies():
            sys.exit(1)
        
        # Re-check after installation
        if not check_dependencies():
            sys.exit(1)
    
    # Check environment
    check_environment()
    
    # Test imports
    if not test_imports():
        logger.error("Critical imports failed. Check for syntax errors or missing dependencies.")
        sys.exit(1)
    
    # Start the server
    logger.info("All checks passed. Starting server...")
    start_server()

if __name__ == "__main__":
    main()