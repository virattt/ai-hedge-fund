import asyncio
import os
import sys
import platform
import subprocess
import time
import re
import json
import queue
import threading
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator
import logging
import signal
import ollama

logger = logging.getLogger(__name__)

class OllamaService:
    """Service for managing Ollama integration in the backend."""
    
    def __init__(self):
        self._status_cache = {}
        self._last_check = 0
        self._cache_duration = 10
        self._download_progress = {}
        self._download_processes = {}
        
        # Initialize async client
        self._async_client = ollama.AsyncClient()
        self._sync_client = ollama.Client()
    
    # =============================================================================
    # PUBLIC API METHODS
    # =============================================================================
    
    async def check_ollama_status(self) -> Dict[str, any]:
        """Check Ollama installation and server status."""
        if self._should_use_cached_status():
            return self._status_cache
        
        try:
            is_installed = await self._check_installation()
            is_running = await self._check_server_running()
            models, server_url = await self._get_server_info(is_running)
            
            status = {
                "installed": is_installed,
                "running": is_running,
                "server_running": is_running,  # Backward compatibility
                "available_models": models,
                "server_url": server_url,
                "error": None
            }
            
            self._update_status_cache(status)
            logger.debug(f"Ollama status: installed={is_installed}, running={is_running}, models={len(models)}")
            return status
            
        except Exception as e:
            logger.error(f"Error checking Ollama status: {e}")
            error_status = self._create_error_status(str(e))
            self._update_status_cache(error_status)
            return error_status
    
    async def start_server(self) -> Dict[str, any]:
        """Start the Ollama server."""
        try:
            success = await self._execute_server_start()
            self._clear_status_cache()
            
            message = "Ollama server started successfully" if success else "Failed to start Ollama server"
            return {"success": success, "message": message}
                
        except Exception as e:
            logger.error(f"Error starting Ollama server: {e}")
            return {"success": False, "message": f"Error starting server: {str(e)}"}
    
    async def stop_server(self) -> Dict[str, any]:
        """Stop the Ollama server."""
        try:
            success = await self._execute_server_stop()
            self._clear_status_cache()
            
            message = "Ollama server stopped successfully" if success else "Failed to stop Ollama server"
            return {"success": success, "message": message}
                
        except Exception as e:
            logger.error(f"Error stopping Ollama server: {e}")
            return {"success": False, "message": f"Error stopping server: {str(e)}"}
    
    async def download_model(self, model_name: str) -> Dict[str, any]:
        """Download an Ollama model."""
        try:
            self._clear_status_cache()
            success = await self._execute_model_download(model_name)
            self._clear_status_cache()
            
            message = f"Model {model_name} downloaded successfully" if success else f"Failed to download model {model_name}"
            return {"success": success, "message": message}
                
        except Exception as e:
            logger.error(f"Error downloading model {model_name}: {e}")
            return {"success": False, "message": f"Error downloading model: {str(e)}"}
    
    async def download_model_with_progress(self, model_name: str) -> AsyncGenerator[str, None]:
        """Download an Ollama model with progress streaming."""
        async for progress_data in self._stream_model_download(model_name):
            yield progress_data
    
    async def delete_model(self, model_name: str) -> Dict[str, any]:
        """Delete an Ollama model."""
        try:
            self._clear_status_cache()
            success = await self._execute_model_deletion(model_name)
            self._clear_status_cache()
            
            message = f"Model {model_name} deleted successfully" if success else f"Failed to delete model {model_name}"
            return {"success": success, "message": message}
                
        except Exception as e:
            logger.error(f"Error deleting model {model_name}: {e}")
            return {"success": False, "message": f"Error deleting model: {str(e)}"}
    
    async def get_recommended_models(self) -> List[Dict[str, str]]:
        """Get list of recommended Ollama models."""
        try:
            models_path = self._get_ollama_models_path()
            
            if models_path.exists():
                return self._load_models_from_file(models_path)
            else:
                return self._get_fallback_models()
                
        except Exception as e:
            logger.error(f"Error loading recommended models: {e}")
            return []
    
    async def get_available_models(self) -> List[Dict[str, str]]:
        """Get available Ollama models formatted for the language models API.
        
        Returns only models that are:
        1. Server is running
        2. Model is downloaded locally  
        3. Model is in our recommended list (OLLAMA_MODELS)
        """
        try:
            status = await self.check_ollama_status()
            
            if not status.get("server_running", False):
                logger.debug("Ollama server not running, returning no models for API")
                return []
            
            downloaded_models = status.get("available_models", [])
            if not downloaded_models:
                logger.debug("No Ollama models downloaded, returning empty list for API")
                return []
            
            api_models = self._format_models_for_api(downloaded_models)
            logger.debug(f"Returning {len(api_models)} Ollama models for language models API")
            return api_models
            
        except Exception as e:
            logger.error(f"Error getting available models for API: {e}")
            return []  # Return empty list on error to not break the API
    
    def get_download_progress(self, model_name: str) -> Optional[Dict[str, any]]:
        """Get current download progress for a model."""
        return self._download_progress.get(model_name)
    
    def get_all_download_progress(self) -> Dict[str, Dict[str, any]]:
        """Get current download progress for all models."""
        return self._download_progress.copy()
    
    def cancel_download(self, model_name: str) -> bool:
        """Cancel an active download."""
        logger.warning(f"Download cancellation not directly supported by ollama client for model: {model_name}")
        
        if model_name in self._download_progress:
            self._download_progress[model_name] = {
                "status": "cancelled",
                "message": f"Download of {model_name} was cancelled",
                "error": "Download cancelled by user"
            }
            return True
        
        return False
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _should_use_cached_status(self) -> bool:
        """Check if we should use cached status."""
        current_time = time.time()
        return (current_time - self._last_check) < self._cache_duration and self._status_cache
    
    def _update_status_cache(self, status: Dict[str, any]) -> None:
        """Update the status cache."""
        self._status_cache = status
        self._last_check = time.time()
    
    def _clear_status_cache(self) -> None:
        """Clear the status cache to force fresh check."""
        self._status_cache = {}
        self._last_check = 0
    
    def _create_error_status(self, error: str) -> Dict[str, any]:
        """Create error status response."""
        return {
            "installed": False,
            "running": False,
            "server_running": False,
            "available_models": [],
            "server_url": "",
            "error": error
        }
    
    async def _check_installation(self) -> bool:
        """Check if Ollama CLI is installed."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._is_ollama_installed)
    
    def _is_ollama_installed(self) -> bool:
        """Check if Ollama is installed on the system."""
        system = platform.system().lower()
        command = ["which", "ollama"] if system in ["darwin", "linux"] else ["where", "ollama"]
        shell = system == "windows"
        
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=shell)
            return result.returncode == 0
        except Exception:
            return False
    
    async def _check_server_running(self) -> bool:
        """Check if the Ollama server is running using the ollama client."""
        try:
            await self._async_client.list()
            logger.debug("Ollama server confirmed running via client")
            return True
        except Exception as e:
            logger.debug(f"Ollama server not reachable: {e}")
            return False
    
    async def _get_server_info(self, is_running: bool) -> tuple[List[str], str]:
        """Get server information (models and URL) if server is running."""
        if not is_running:
            return [], ""
        
        try:
            response = await self._async_client.list()
            models = [model.model for model in response.models]
            server_url = getattr(self._async_client, 'host', 'http://localhost:11434')
            logger.debug(f"Found {len(models)} locally available models")
            return models, server_url
        except Exception as e:
            logger.debug(f"Failed to get server info: {e}")
            return [], ""
    
    async def _execute_server_start(self) -> bool:
        """Execute server start operation."""
        # Check if already running
        try:
            self._sync_client.list()
            logger.info("Ollama server is already running")
            return True
        except Exception:
            pass  # Server not running, continue to start it
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._start_ollama_process)
    
    def _start_ollama_process(self) -> bool:
        """Start the Ollama server process."""
        system = platform.system().lower()
        
        try:
            command = ["ollama", "serve"]
            shell = system == "windows"
            subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell)
            
            return self._wait_for_server_start()
            
        except Exception as e:
            logger.error(f"Error starting Ollama server: {e}")
            return False
    
    def _wait_for_server_start(self) -> bool:
        """Wait for server to start and become ready."""
        logger.info("Starting Ollama server, waiting for it to become ready...")
        
        for i in range(20):  # Try for 20 seconds
            time.sleep(1)
            try:
                self._sync_client.list()
                logger.info(f"Ollama server started successfully after {i+1} seconds")
                return True
            except Exception:
                logger.debug(f"Waiting for Ollama server... ({i+1}/20)")
                continue
        
        logger.error("Ollama server failed to start within 20 seconds")
        return False
    
    async def _execute_server_stop(self) -> bool:
        """Execute server stop operation."""
        # Check if already stopped
        try:
            self._sync_client.list()
        except Exception:
            logger.info("Ollama server is already stopped")
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._stop_ollama_process)
    
    def _stop_ollama_process(self) -> bool:
        """Stop the Ollama server process."""
        system = platform.system().lower()
        
        try:
            if system in ["darwin", "linux"]:
                return self._stop_unix_process()
            elif system == "windows":
                return self._stop_windows_process()
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error stopping Ollama server: {e}")
            return False
    
    def _stop_unix_process(self) -> bool:
        """Stop Ollama on Unix-like systems."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ollama serve"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            if result.returncode == 0:
                pids = [pid for pid in result.stdout.strip().split('\n') if pid]
                self._terminate_processes(pids)
            
            return self._verify_server_stopped()
            
        except Exception as e:
            logger.error(f"Error stopping Unix process: {e}")
            return False
    
    def _stop_windows_process(self) -> bool:
        """Stop Ollama on Windows."""
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "ollama.exe"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            return self._verify_server_stopped()
            
        except Exception as e:
            logger.error(f"Error stopping Windows process: {e}")
            return False
    
    def _terminate_processes(self, pids: List[str]) -> None:
        """Terminate processes gracefully, then forcefully if needed."""
        # Try SIGTERM first
        for pid in pids:
            if pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except (ValueError, ProcessLookupError, PermissionError):
                    continue
        
        # Wait for graceful termination
        for _ in range(5):
            try:
                self._sync_client.list()
                time.sleep(1)
            except Exception:
                return  # Server stopped
        
        # Force kill if still running
        for pid in pids:
            if pid:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except (ValueError, ProcessLookupError, PermissionError):
                    continue
    
    def _verify_server_stopped(self) -> bool:
        """Verify that the server has stopped."""
        for _ in range(3):
            try:
                self._sync_client.list()
                time.sleep(1)
            except Exception:
                return True
        return False
    
    async def _execute_model_download(self, model_name: str) -> bool:
        """Execute model download operation."""
        if not await self._check_server_running():
            logger.error(f"Cannot download model {model_name}: Ollama server is not running")
            return False
        
        try:
            logger.info(f"Starting download of model: {model_name}")
            await self._async_client.pull(model_name)
            logger.info(f"Successfully downloaded model: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Error downloading model {model_name}: {e}")
            return False
    
    async def _execute_model_deletion(self, model_name: str) -> bool:
        """Execute model deletion operation."""
        if not await self._check_server_running():
            logger.error(f"Cannot delete model {model_name}: Ollama server is not running")
            return False
        
        try:
            logger.info(f"Deleting model: {model_name}")
            await self._async_client.delete(model_name)
            logger.info(f"Successfully deleted model: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting model {model_name}: {e}")
            return False
    
    async def _stream_model_download(self, model_name: str) -> AsyncGenerator[str, None]:
        """Stream model download with progress updates."""
        try:
            if not await self._check_server_running():
                yield f"data: {json.dumps({'status': 'error', 'error': 'Ollama server is not running'})}\n\n"
                return
            
            logger.info(f"Starting download of model: {model_name}")
            self._download_progress[model_name] = {"status": "starting", "percentage": 0}
            
            yield f"data: {json.dumps({'status': 'starting', 'percentage': 0, 'message': f'Starting download of {model_name}...'})}\n\n"
            
            async for progress in self._async_client.pull(model_name, stream=True):
                progress_data = self._process_download_progress(progress, model_name)
                if progress_data:
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    
                    if progress_data.get("status") == "completed":
                        logger.info(f"Successfully downloaded model: {model_name}")
                        break
                        
        except Exception as e:
            error_data = {
                "status": "error",
                "message": f"Error downloading model {model_name}",
                "error": str(e)
            }
            self._download_progress[model_name] = error_data
            yield f"data: {json.dumps(error_data)}\n\n"
            logger.error(f"Error downloading model {model_name}: {e}")
        finally:
            await asyncio.sleep(1)
            if model_name in self._download_progress:
                del self._download_progress[model_name]
    
    def _process_download_progress(self, progress, model_name: str) -> Optional[Dict[str, any]]:
        """Process download progress from ollama client."""
        if not hasattr(progress, 'status'):
            return None
        
        progress_data = {
            "status": "downloading",
            "message": progress.status,
            "raw_output": progress.status
        }
        
        # Add completed/total info if available
        if hasattr(progress, 'completed') and hasattr(progress, 'total') and progress.total > 0:
            percentage = (progress.completed / progress.total) * 100
            progress_data.update({
                "percentage": percentage,
                "bytes_downloaded": progress.completed,
                "total_bytes": progress.total
            })
        
        # Add digest info if available
        if hasattr(progress, 'digest'):
            progress_data["digest"] = progress.digest
        
        # Store in cache
        self._download_progress[model_name] = progress_data
        
        # Check if download is complete
        if (progress.status == "success" or 
            (hasattr(progress, 'completed') and hasattr(progress, 'total') and 
             progress.completed == progress.total)):
            final_data = {
                "status": "completed",
                "percentage": 100,
                "message": f"Model {model_name} downloaded successfully!"
            }
            self._download_progress[model_name] = final_data
            return final_data
        
        return progress_data
    
    def _get_ollama_models_path(self) -> Path:
        """Get path to ollama_models.json file."""
        return Path(__file__).parent.parent.parent.parent / "src" / "llm" / "ollama_models.json"
    
    def _load_models_from_file(self, models_path: Path) -> List[Dict[str, str]]:
        """Load models from JSON file."""
        with open(models_path, 'r') as f:
            return json.load(f)
    
    def _get_fallback_models(self) -> List[Dict[str, str]]:
        """Get fallback models when file is not available."""
        return [
            {"display_name": "[meta] llama3.1 (8B)", "model_name": "llama3.1:latest", "provider": "Ollama"},
            {"display_name": "[google] gemma3 (4B)", "model_name": "gemma3:4b", "provider": "Ollama"},
            {"display_name": "[alibaba] qwen3 (4B)", "model_name": "qwen3:4b", "provider": "Ollama"},
        ]
    
    def _format_models_for_api(self, downloaded_models: List[str]) -> List[Dict[str, str]]:
        """Format downloaded models for API response."""
        # Import OLLAMA_MODELS here to avoid circular imports
        from src.llm.models import OLLAMA_MODELS
        
        api_models = []
        for ollama_model in OLLAMA_MODELS:
            if ollama_model.model_name in downloaded_models:
                api_models.append({
                    "display_name": ollama_model.display_name,
                    "model_name": ollama_model.model_name,
                    "provider": "Ollama"
                })
        
        return api_models

# Global service instance
ollama_service = OllamaService() 