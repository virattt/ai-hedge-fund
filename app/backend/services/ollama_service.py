import asyncio
import os
import sys
import platform
import subprocess
import requests
import time
import re
import json
import queue
import threading
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator
import logging
import signal

logger = logging.getLogger(__name__)

# Ollama server configuration
OLLAMA_SERVER_URL = "http://localhost:11434"
OLLAMA_API_MODELS_ENDPOINT = f"{OLLAMA_SERVER_URL}/api/tags"
OLLAMA_API_VERSION_ENDPOINT = f"{OLLAMA_SERVER_URL}/api/version"

class OllamaService:
    """Service for managing Ollama integration in the backend."""
    
    def __init__(self):
        self._status_cache = {}
        self._last_check = 0
        self._cache_duration = 10  # Reduce cache duration to 10 seconds for better responsiveness
        self._download_progress = {}  # Track download progress for models
        self._download_processes = {}  # Track active download processes for cancellation
    
    def _is_ollama_installed(self) -> bool:
        """Check if Ollama is installed on the system."""
        system = platform.system().lower()
        
        if system == "darwin" or system == "linux":  # macOS or Linux
            try:
                result = subprocess.run(["which", "ollama"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                return result.returncode == 0
            except Exception:
                return False
        elif system == "windows":  # Windows
            try:
                result = subprocess.run(["where", "ollama"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
                return result.returncode == 0
            except Exception:
                return False
        else:
            return False  # Unsupported OS
    
    def _is_ollama_server_running(self) -> bool:
        """Check if the Ollama server is running using multiple endpoints."""
        # Try multiple endpoints to ensure server is actually ready
        endpoints_to_try = [
            OLLAMA_API_VERSION_ENDPOINT,  # Try version endpoint first
            OLLAMA_SERVER_URL,            # Try root endpoint
            OLLAMA_API_MODELS_ENDPOINT    # Try models endpoint as fallback
        ]
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.get(endpoint, timeout=3)
                if response.status_code == 200:
                    logger.debug(f"Ollama server confirmed running via {endpoint}")
                    return True
            except requests.RequestException as e:
                logger.debug(f"Failed to connect to {endpoint}: {e}")
                continue
        
        logger.debug("Ollama server not reachable on any endpoint")
        return False
    
    def _get_locally_available_models(self) -> List[str]:
        """Get a list of models that are already downloaded locally."""
        if not self._is_ollama_server_running():
            return []
        
        try:
            response = requests.get(OLLAMA_API_MODELS_ENDPOINT, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data["models"]] if "models" in data else []
            return []
        except requests.RequestException as e:
            logger.debug(f"Failed to get models: {e}")
            return []
    
    def _start_ollama_server(self) -> bool:
        """Start the Ollama server if it's not already running."""
        if self._is_ollama_server_running():
            return True
        
        system = platform.system().lower()
        
        try:
            if system == "darwin" or system == "linux":  # macOS or Linux
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            elif system == "windows":  # Windows
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            else:
                return False
            
            # Wait for server to start with increased timeout and better checking
            logger.info("Starting Ollama server, waiting for it to become ready...")
            for i in range(20):  # Try for 20 seconds
                time.sleep(1)  # Wait a bit before each check
                if self._is_ollama_server_running():
                    logger.info(f"Ollama server started successfully after {i+1} seconds")
                    return True
                logger.debug(f"Waiting for Ollama server... ({i+1}/20)")
            
            logger.error("Ollama server failed to start within 20 seconds")
            return False
        except Exception as e:
            logger.error(f"Error starting Ollama server: {e}")
            return False
    
    def _stop_ollama_server(self) -> bool:
        """Stop the Ollama server by terminating the ollama serve process."""
        if not self._is_ollama_server_running():
            return True  # Already stopped
        
        system = platform.system().lower()
        
        try:
            if system == "darwin" or system == "linux":  # macOS or Linux
                # Find and kill ollama serve processes
                result = subprocess.run(
                    ["pgrep", "-f", "ollama serve"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                
                if result.returncode == 0:
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid:
                            try:
                                os.kill(int(pid), signal.SIGTERM)
                            except (ValueError, ProcessLookupError, PermissionError):
                                continue
                    
                    # Wait for processes to terminate
                    for _ in range(5):  # Try for 5 seconds
                        if not self._is_ollama_server_running():
                            return True
                        time.sleep(1)
                    
                    # If still running, try SIGKILL
                    for pid in pids:
                        if pid:
                            try:
                                os.kill(int(pid), signal.SIGKILL)
                            except (ValueError, ProcessLookupError, PermissionError):
                                continue
                
            elif system == "windows":  # Windows
                # Use taskkill to stop ollama processes
                subprocess.run(
                    ["taskkill", "/F", "/IM", "ollama.exe"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
            
            # Final check
            for _ in range(3):  # Try for 3 seconds
                if not self._is_ollama_server_running():
                    return True
                time.sleep(1)
            
            return False
            
        except Exception as e:
            logger.error(f"Error stopping Ollama server: {e}")
            return False
    
    def _parse_progress(self, output: str) -> Optional[Dict[str, any]]:
        """Parse progress information from Ollama output."""
        if not output:
            return None
            
        # Initialize progress data
        progress_data = {
            "percentage": None,
            "phase": None,
            "bytes_downloaded": None,
            "total_bytes": None,
            "speed": None
        }
        
        # Look for percentage
        percentage_match = re.search(r"(\d+(?:\.\d+)?)%", output)
        if percentage_match:
            try:
                progress_data["percentage"] = float(percentage_match.group(1))
            except ValueError:
                pass
        
        # Look for phase (downloading, extracting, etc.)
        phase_match = re.search(r"^([a-zA-Z\s]+):", output)
        if phase_match:
            progress_data["phase"] = phase_match.group(1).strip()
        
        # Look for bytes information: "23.45 MB / 42.19 MB"
        bytes_match = re.search(r"(\d+(?:\.\d+)?)\s*([KMGT]?B)\s*/\s*(\d+(?:\.\d+)?)\s*([KMGT]?B)", output)
        if bytes_match:
            try:
                downloaded = float(bytes_match.group(1))
                downloaded_unit = bytes_match.group(2)
                total = float(bytes_match.group(3))
                total_unit = bytes_match.group(4)
                
                # Convert to bytes
                units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
                progress_data["bytes_downloaded"] = int(downloaded * units.get(downloaded_unit, 1))
                progress_data["total_bytes"] = int(total * units.get(total_unit, 1))
            except (ValueError, KeyError):
                pass
        
        return progress_data if any(v is not None for v in progress_data.values()) else None
    
    async def _download_model_with_progress(self, model_name: str) -> AsyncGenerator[str, None]:
        """Download an Ollama model with progress streaming."""
        if not self._is_ollama_server_running():
            yield f"data: {json.dumps({'error': 'Ollama server is not running'})}\n\n"
            return
        
        try:
            logger.info(f"Starting download of model: {model_name}")
            self._download_progress[model_name] = {"status": "starting", "percentage": 0}
            
            # Initialize progress
            yield f"data: {json.dumps({'status': 'starting', 'percentage': 0, 'message': f'Starting download of {model_name}...'})}\n\n"
            
            # Create a queue for communication between the thread and async generator
            progress_queue = queue.Queue()
            download_complete = threading.Event()
            
            def download_in_thread():
                """Run the download process in a separate thread."""
                process = None
                try:
                    # Start the download process
                    process = subprocess.Popen(
                        ["ollama", "pull", model_name],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        encoding='utf-8',
                        errors='replace'
                    )
                    
                    # Store the process for potential cancellation
                    self._download_processes[model_name] = process
                    
                    last_percentage = 0
                    last_phase = ""
                    
                    while True:
                        output = process.stdout.readline()
                        if output == "" and process.poll() is not None:
                            break
                            
                        if output:
                            output = output.strip()
                            if output:  # Only process non-empty lines
                                progress = self._parse_progress(output)
                                
                                if progress:
                                    # Update progress data
                                    update_data = {
                                        "status": "downloading",
                                        "message": output,
                                        "raw_output": output
                                    }
                                    
                                    if progress["percentage"] is not None:
                                        update_data["percentage"] = progress["percentage"]
                                        last_percentage = progress["percentage"]
                                    
                                    if progress["phase"]:
                                        update_data["phase"] = progress["phase"]
                                        last_phase = progress["phase"]
                                    
                                    if progress["bytes_downloaded"] and progress["total_bytes"]:
                                        update_data["bytes_downloaded"] = progress["bytes_downloaded"]
                                        update_data["total_bytes"] = progress["total_bytes"]
                                    
                                    # Store in cache
                                    self._download_progress[model_name] = update_data
                                    
                                    # Send update to queue
                                    progress_queue.put(update_data)
                                else:
                                    # Send raw output even if we can't parse progress
                                    update_data = {
                                        "status": "downloading",
                                        "message": output,
                                        "raw_output": output
                                    }
                                    if last_percentage > 0:
                                        update_data["percentage"] = last_percentage
                                    if last_phase:
                                        update_data["phase"] = last_phase
                                    
                                    progress_queue.put(update_data)
                    
                    # Check final result
                    return_code = process.wait()
                    
                    if return_code == 0:
                        final_data = {
                            "status": "completed",
                            "percentage": 100,
                            "message": f"Model {model_name} downloaded successfully!"
                        }
                        self._download_progress[model_name] = final_data
                        progress_queue.put(final_data)
                        logger.info(f"Successfully downloaded model: {model_name}")
                    else:
                        # Check if it was cancelled (return code -15 or -9 typically means terminated)
                        if return_code in [-15, -9]:  # SIGTERM or SIGKILL
                            error_data = {
                                "status": "cancelled",
                                "message": f"Download of {model_name} was cancelled",
                                "error": "Download cancelled by user"
                            }
                        else:
                            error_data = {
                                "status": "error",
                                "message": f"Failed to download model {model_name}",
                                "error": f"Process exited with code {return_code}"
                            }
                        self._download_progress[model_name] = error_data
                        progress_queue.put(error_data)
                        logger.error(f"Failed to download model {model_name}: exit code {return_code}")
                        
                except Exception as e:
                    error_data = {
                        "status": "error",
                        "message": f"Error downloading model {model_name}",
                        "error": str(e)
                    }
                    self._download_progress[model_name] = error_data
                    progress_queue.put(error_data)
                    logger.error(f"Error downloading model {model_name}: {e}")
                finally:
                    # Clean up process reference
                    if model_name in self._download_processes:
                        del self._download_processes[model_name]
                    download_complete.set()
            
            # Start the download in a separate thread
            download_thread = threading.Thread(target=download_in_thread, daemon=True)
            download_thread.start()
            
            # Yield progress updates as they come in
            while True:
                try:
                    # Check for new progress with a timeout to keep the connection alive
                    try:
                        # Use run_in_executor to make the queue.get non-blocking for the event loop
                        loop = asyncio.get_event_loop()
                        progress_data = await loop.run_in_executor(
                            None, 
                            lambda: progress_queue.get(timeout=0.5)
                        )
                        yield f"data: {json.dumps(progress_data)}\n\n"
                        
                        # Check if download is complete or failed
                        if progress_data.get("status") in ["completed", "error"]:
                            break
                            
                    except queue.Empty:
                        # Send a heartbeat to keep connection alive and yield control
                        if download_complete.is_set():
                            break
                        # Yield control back to the event loop
                        await asyncio.sleep(0.1)
                        continue
                        
                except Exception as e:
                    logger.error(f"Error in progress streaming: {e}")
                    break
            
            # Wait for the download thread to finish (non-blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: download_thread.join(timeout=5))
                
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
            # Clean up progress tracking after a short delay
            await asyncio.sleep(1)  # Reduced from 5 seconds to 1 second
            if model_name in self._download_progress:
                del self._download_progress[model_name]
    
    def _download_model(self, model_name: str) -> bool:
        """Download an Ollama model (legacy synchronous version)."""
        if not self._is_ollama_server_running():
            logger.error(f"Cannot download model {model_name}: Ollama server is not running")
            return False
        
        try:
            logger.info(f"Starting download of model: {model_name}")
            # Use the Ollama CLI to download the model
            process = subprocess.run(["ollama", "pull", model_name], capture_output=True, text=True, timeout=600)
            if process.returncode == 0:
                logger.info(f"Successfully downloaded model: {model_name}")
                return True
            else:
                logger.error(f"Failed to download model {model_name}: {process.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error downloading model {model_name}: {e}")
            return False
    
    def _delete_model(self, model_name: str) -> bool:
        """Delete an Ollama model."""
        if not self._is_ollama_server_running():
            logger.error(f"Cannot delete model {model_name}: Ollama server is not running")
            return False
        
        try:
            logger.info(f"Deleting model: {model_name}")
            # Use the Ollama CLI to delete the model
            process = subprocess.run(["ollama", "rm", model_name], capture_output=True, text=True)
            if process.returncode == 0:
                logger.info(f"Successfully deleted model: {model_name}")
                return True
            else:
                logger.error(f"Failed to delete model {model_name}: {process.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error deleting model {model_name}: {e}")
            return False
    
    def get_download_progress(self, model_name: str) -> Optional[Dict[str, any]]:
        """Get current download progress for a model."""
        return self._download_progress.get(model_name)
    
    def get_all_download_progress(self) -> Dict[str, Dict[str, any]]:
        """Get current download progress for all models."""
        return self._download_progress.copy()
    
    async def check_ollama_status(self) -> Dict[str, any]:
        """Check Ollama installation and server status."""
        current_time = time.time()
        
        # Use cached result if recent
        if (current_time - self._last_check) < self._cache_duration and self._status_cache:
            return self._status_cache
        
        # Run blocking operations in thread pool
        loop = asyncio.get_event_loop()
        
        try:
            is_installed = await loop.run_in_executor(None, self._is_ollama_installed)
            is_running = await loop.run_in_executor(None, self._is_ollama_server_running)
            
            models = []
            if is_running:
                models = await loop.run_in_executor(None, self._get_locally_available_models)
            
            status = {
                "installed": is_installed,
                "running": is_running,
                "available_models": models,
                "server_url": OLLAMA_SERVER_URL,
                "error": None
            }
            
            # Update cache
            self._status_cache = status
            self._last_check = current_time
            
            logger.debug(f"Ollama status: installed={is_installed}, running={is_running}, models={len(models)}")
            return status
            
        except Exception as e:
            logger.error(f"Error checking Ollama status: {e}")
            error_status = {
                "installed": False,
                "running": False,
                "available_models": [],
                "server_url": OLLAMA_SERVER_URL,
                "error": str(e)
            }
            self._status_cache = error_status
            self._last_check = current_time
            return error_status
    
    async def start_server(self) -> Dict[str, any]:
        """Start the Ollama server."""
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._start_ollama_server)
            
            # Clear cache to force fresh status check
            self._status_cache = {}
            self._last_check = 0
            
            if success:
                return {"success": True, "message": "Ollama server started successfully"}
            else:
                return {"success": False, "message": "Failed to start Ollama server"}
                
        except Exception as e:
            logger.error(f"Error starting Ollama server: {e}")
            return {"success": False, "message": f"Error starting server: {str(e)}"}
    
    async def stop_server(self) -> Dict[str, any]:
        """Stop the Ollama server."""
        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._stop_ollama_server)
            
            # Clear cache to force fresh status check
            self._status_cache = {}
            self._last_check = 0
            
            if success:
                return {"success": True, "message": "Ollama server stopped successfully"}
            else:
                return {"success": False, "message": "Failed to stop Ollama server"}
                
        except Exception as e:
            logger.error(f"Error stopping Ollama server: {e}")
            return {"success": False, "message": f"Error stopping server: {str(e)}"}
    
    async def download_model(self, model_name: str) -> Dict[str, any]:
        """Download an Ollama model (legacy synchronous version)."""
        try:
            # Force fresh status check before download
            self._status_cache = {}
            self._last_check = 0
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._download_model, model_name)
            
            # Clear cache to force fresh status check
            self._status_cache = {}
            self._last_check = 0
            
            if success:
                return {"success": True, "message": f"Model {model_name} downloaded successfully"}
            else:
                return {"success": False, "message": f"Failed to download model {model_name}"}
                
        except Exception as e:
            logger.error(f"Error downloading model {model_name}: {e}")
            return {"success": False, "message": f"Error downloading model: {str(e)}"}
    
    async def download_model_with_progress(self, model_name: str) -> AsyncGenerator[str, None]:
        """Download an Ollama model with progress streaming."""
        async for progress_data in self._download_model_with_progress(model_name):
            yield progress_data
    
    async def delete_model(self, model_name: str) -> Dict[str, any]:
        """Delete an Ollama model."""
        try:
            # Force fresh status check before delete
            self._status_cache = {}
            self._last_check = 0
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._delete_model, model_name)
            
            # Clear cache to force fresh status check
            self._status_cache = {}
            self._last_check = 0
            
            if success:
                return {"success": True, "message": f"Model {model_name} deleted successfully"}
            else:
                return {"success": False, "message": f"Failed to delete model {model_name}"}
                
        except Exception as e:
            logger.error(f"Error deleting model {model_name}: {e}")
            return {"success": False, "message": f"Error deleting model: {str(e)}"}
    
    async def get_recommended_models(self) -> List[Dict[str, str]]:
        """Get list of recommended Ollama models."""
        # Load from the existing ollama_models.json
        try:
            import json
            ollama_models_path = Path(__file__).parent.parent.parent.parent / "src" / "llm" / "ollama_models.json"
            
            if ollama_models_path.exists():
                with open(ollama_models_path, 'r') as f:
                    models_data = json.load(f)
                return models_data
            else:
                # Fallback to basic recommendations
                return [
                    {"display_name": "[meta] llama3.1 (8B)", "model_name": "llama3.1:latest", "provider": "Ollama"},
                    {"display_name": "[google] gemma3 (4B)", "model_name": "gemma3:4b", "provider": "Ollama"},
                    {"display_name": "[alibaba] qwen3 (4B)", "model_name": "qwen3:4b", "provider": "Ollama"},
                ]
                
        except Exception as e:
            logger.error(f"Error loading recommended models: {e}")
            return []
    
    def cancel_download(self, model_name: str) -> bool:
        """Cancel an active download."""
        if model_name not in self._download_processes:
            logger.warning(f"No active download found for model: {model_name}")
            return False
        
        try:
            process = self._download_processes[model_name]
            if process and process.poll() is None:  # Process is still running
                logger.info(f"Cancelling download for model: {model_name}")
                process.terminate()
                
                # Give it a moment to terminate gracefully
                time.sleep(1)
                
                # If still running, force kill
                if process.poll() is None:
                    process.kill()
                
                # Update progress to show cancellation
                self._download_progress[model_name] = {
                    "status": "cancelled",
                    "message": f"Download of {model_name} was cancelled",
                    "error": "Download cancelled by user"
                }
                
                logger.info(f"Successfully cancelled download for model: {model_name}")
                return True
            else:
                logger.warning(f"Process for {model_name} is not running or already finished")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling download for {model_name}: {e}")
            return False

# Global service instance
ollama_service = OllamaService() 