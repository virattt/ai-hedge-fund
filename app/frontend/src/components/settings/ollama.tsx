import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { AlertTriangle, Brain, CheckCircle, Download, Play, RefreshCw, Server, Square, Trash2, X } from 'lucide-react';
import { useEffect, useState } from 'react';

interface OllamaStatus {
  installed: boolean;
  running: boolean;
  available_models: string[];
  server_url: string;
  error?: string;
}

interface RecommendedModel {
  display_name: string;
  model_name: string;
  provider: string;
}

interface ModelWithStatus extends RecommendedModel {
  isDownloaded: boolean;
}

interface DownloadProgress {
  status: string;
  percentage?: number;
  message?: string;
  phase?: string;
  bytes_downloaded?: number;
  total_bytes?: number;
  error?: string;
}

export function OllamaSettings() {
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null);
  const [recommendedModels, setRecommendedModels] = useState<RecommendedModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<Record<string, DownloadProgress>>({});
  const [activeDownloads, setActiveDownloads] = useState<Set<string>>(new Set());
  const [pollIntervals, setPollIntervals] = useState<Set<NodeJS.Timeout>>(new Set());
  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    isOpen: boolean;
    modelName: string;
    displayName: string;
  }>({
    isOpen: false,
    modelName: '',
    displayName: ''
  });
  const [cancellingDownloads, setCancellingDownloads] = useState<Set<string>>(new Set());

  const fetchOllamaStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/ollama/status');
      if (response.ok) {
        const status = await response.json();
        setOllamaStatus(status);
        setError(null);
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`Failed to get status: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Failed to fetch Ollama status:', error);
      setError('Failed to connect to backend service');
    }
  };

  const fetchRecommendedModels = async () => {
    try {
      const response = await fetch('http://localhost:8000/ollama/models/recommended');
      if (response.ok) {
        const models = await response.json();
        setRecommendedModels(models);
      } else {
        console.error('Failed to fetch recommended models');
      }
    } catch (error) {
      console.error('Failed to fetch recommended models:', error);
    }
  };

  const startOllamaServer = async () => {
    setActionLoading('start-server');
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/ollama/start', {
        method: 'POST',
      });
      if (response.ok) {
        await fetchOllamaStatus();
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`Failed to start server: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Failed to start Ollama server:', error);
      setError('Failed to start Ollama server');
    }
    setActionLoading(null);
  };

  const stopOllamaServer = async () => {
    setActionLoading('stop-server');
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/ollama/stop', {
        method: 'POST',
      });
      if (response.ok) {
        await fetchOllamaStatus();
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`Failed to stop server: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Failed to stop Ollama server:', error);
      setError('Failed to stop Ollama server');
    }
    setActionLoading(null);
  };

  const downloadModelWithProgress = async (modelName: string) => {
    setError(null);
    setActiveDownloads(prev => new Set(prev).add(modelName));
    setDownloadProgress(prev => ({
      ...prev,
      [modelName]: { status: 'starting', percentage: 0, message: 'Initializing download...' }
    }));

    try {
      // Make a POST request to the progress endpoint which returns a streaming response
      const response = await fetch('http://localhost:8000/ollama/models/download/progress', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ model_name: modelName }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`Failed to start download for ${modelName}: ${errorData.detail}`);
        setActiveDownloads(prev => {
          const newSet = new Set(prev);
          newSet.delete(modelName);
          return newSet;
        });
        return;
      }

      // Read the streaming response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const jsonData = line.slice(6).trim();
                  if (jsonData) {
                    const data = JSON.parse(jsonData);
                    
                    setDownloadProgress(prev => ({
                      ...prev,
                      [modelName]: data
                    }));

                    // Check if download is complete or failed
                    if (data.status === 'completed') {
                      setActiveDownloads(prev => {
                        const newSet = new Set(prev);
                        newSet.delete(modelName);
                        return newSet;
                      });
                      // Immediately clean up progress display for completed downloads
                      setDownloadProgress(prev => {
                        const newProgress = { ...prev };
                        delete newProgress[modelName];
                        return newProgress;
                      });
                      // Refresh status to show the new model
                      setTimeout(() => fetchOllamaStatus(), 1000);
                      return; // Exit the function
                    } else if (data.status === 'error' || data.status === 'cancelled') {
                      setActiveDownloads(prev => {
                        const newSet = new Set(prev);
                        newSet.delete(modelName);
                        return newSet;
                      });
                      if (data.status === 'error') {
                        setError(`Download failed for ${modelName}: ${data.message || data.error}`);
                      }
                      // Clean up progress display after 3 seconds for errors/cancellations
                      setTimeout(() => {
                        setDownloadProgress(prev => {
                          const newProgress = { ...prev };
                          delete newProgress[modelName];
                          return newProgress;
                        });
                      }, 3000);
                      return; // Exit the function
                    }
                  }
                } catch (e) {
                  console.error('Error parsing progress data:', e, 'Line:', line);
                }
              }
            }
          }
        } finally {
          reader.releaseLock();
        }
      }
    } catch (error) {
      console.error('Failed to download model with progress:', error);
      setError(`Failed to download ${modelName}: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setActiveDownloads(prev => {
        const newSet = new Set(prev);
        newSet.delete(modelName);
        return newSet;
      });
    }
  };

  const cancelDownload = async (modelName: string) => {
    setError(null);
    setCancellingDownloads(prev => new Set(prev).add(modelName));
    
    try {
      // Call the backend to cancel the download
      const response = await fetch(`http://localhost:8000/ollama/models/download/${encodeURIComponent(modelName)}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        console.log(`Successfully cancelled download for ${modelName}`);
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        console.warn(`Failed to cancel download for ${modelName}: ${errorData.detail}`);
        // Don't show error to user since the UI cleanup will still happen
      }
    } catch (error) {
      console.error('Failed to cancel download:', error);
      // Don't show error to user since the UI cleanup will still happen
    }
    
    // Always clean up the UI state regardless of backend response
    setActiveDownloads(prev => {
      const newSet = new Set(prev);
      newSet.delete(modelName);
      return newSet;
    });
    setDownloadProgress(prev => {
      const newProgress = { ...prev };
      delete newProgress[modelName];
      return newProgress;
    });
    setCancellingDownloads(prev => {
      const newSet = new Set(prev);
      newSet.delete(modelName);
      return newSet;
    });
    
    console.log(`Cancelled download tracking for ${modelName}`);
  };

  const deleteModel = async (modelName: string) => {
    setActionLoading(`delete-${modelName}`);
    setError(null);
    try {
      const response = await fetch(`http://localhost:8000/ollama/models/${encodeURIComponent(modelName)}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        await fetchOllamaStatus();
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`Failed to delete ${modelName}: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Failed to delete model:', error);
      setError(`Failed to delete ${modelName}`);
    }
    setActionLoading(null);
  };

  const confirmDeleteModel = async () => {
    const { modelName } = deleteConfirmation;
    setDeleteConfirmation({ isOpen: false, modelName: '', displayName: '' });
    await deleteModel(modelName);
  };

  const cancelDeleteModel = () => {
    setDeleteConfirmation({ isOpen: false, modelName: '', displayName: '' });
  };

  const refreshStatus = async () => {
    setLoading(true);
    setError(null);
    await Promise.all([fetchOllamaStatus(), fetchRecommendedModels()]);
    setLoading(false);
  };

  const checkForActiveDownloads = async () => {
    // Check if Ollama is running
    if (!ollamaStatus?.running) return;

    try {
      // Get all active downloads in one call instead of checking each model individually
      const response = await fetch('http://localhost:8000/ollama/models/downloads/active');
      if (response.ok) {
        const activeDownloads = await response.json();
        
        // Update state with any active downloads found (only downloading/starting status)
        Object.entries(activeDownloads).forEach(([modelName, progress]) => {
          const progressData = progress as DownloadProgress;
          
          // Only add truly active downloads to avoid showing completed ones on refresh
          if (progressData.status === 'downloading' || progressData.status === 'starting') {
            setActiveDownloads(prev => new Set(prev).add(modelName));
            setDownloadProgress(prev => ({
              ...prev,
              [modelName]: progressData
            }));
            
            // Start monitoring this download
            reconnectToDownload(modelName);
          }
        });
      }
    } catch (error) {
      // Ignore errors - probably no active downloads or server not available
      console.debug('No active downloads found or error checking:', error);
    }
  };

  const reconnectToDownload = async (modelName: string) => {
    // Don't reconnect if we're already tracking this download
    if (activeDownloads.has(modelName)) {
      console.debug(`Already tracking download for ${modelName}`);
      return;
    }

    console.log(`Monitoring existing download for ${modelName}`);
    
    // Poll for progress updates instead of starting a new stream
    const pollProgress = async () => {
      try {
        // Check all active downloads instead of individual model
        const response = await fetch('http://localhost:8000/ollama/models/downloads/active');
        if (response.ok) {
          const activeDownloads = await response.json();
          const progress = activeDownloads[modelName];
          
          if (progress) {
            setDownloadProgress(prev => ({
              ...prev,
              [modelName]: progress
            }));

            // Check if download is complete or failed
            if (progress.status === 'completed') {
              setActiveDownloads(prev => {
                const newSet = new Set(prev);
                newSet.delete(modelName);
                return newSet;
              });
              // Immediately clean up progress display for completed downloads
              setDownloadProgress(prev => {
                const newProgress = { ...prev };
                delete newProgress[modelName];
                return newProgress;
              });
              // Refresh status to show the new model
              setTimeout(() => fetchOllamaStatus(), 1000);
              return false; // Stop polling
            } else if (progress.status === 'error' || progress.status === 'cancelled') {
              setActiveDownloads(prev => {
                const newSet = new Set(prev);
                newSet.delete(modelName);
                return newSet;
              });
              if (progress.status === 'error') {
                setError(`Download failed for ${modelName}: ${progress.message || progress.error}`);
              }
              // Clean up progress display after 3 seconds for errors/cancellations
              setTimeout(() => {
                setDownloadProgress(prev => {
                  const newProgress = { ...prev };
                  delete newProgress[modelName];
                  return newProgress;
                });
              }, 3000);
              return false; // Stop polling
            }
            
            return true; // Continue polling
          } else {
            // Model not in active downloads, remove from tracking
            setActiveDownloads(prev => {
              const newSet = new Set(prev);
              newSet.delete(modelName);
              return newSet;
            });
            return false; // Stop polling
          }
        } else {
          // Error getting active downloads, stop polling
          console.error(`Error getting active downloads: ${response.status}`);
          return false; // Stop polling
        }
      } catch (error) {
        console.error(`Error polling progress for ${modelName}:`, error);
        return false; // Stop polling on error
      }
    };

    // Start polling every 2 seconds
    const pollInterval = setInterval(async () => {
      const shouldContinue = await pollProgress();
      if (!shouldContinue) {
        clearInterval(pollInterval);
        setPollIntervals(prev => {
          const newSet = new Set(prev);
          newSet.delete(pollInterval);
          return newSet;
        });
      }
    }, 2000);

    // Track the interval for cleanup
    setPollIntervals(prev => new Set(prev).add(pollInterval));

    // Do an initial poll
    const shouldContinue = await pollProgress();
    if (!shouldContinue) {
      clearInterval(pollInterval);
      setPollIntervals(prev => {
        const newSet = new Set(prev);
        newSet.delete(pollInterval);
        return newSet;
      });
    }
  };

  useEffect(() => {
    refreshStatus();
  }, []);

  // Check for active downloads after we have status and models data
  useEffect(() => {
    if (ollamaStatus?.running && recommendedModels.length > 0) {
      checkForActiveDownloads();
    }
  }, [ollamaStatus?.running, recommendedModels.length]); // Only depend on running status and whether we have models

  // Cleanup polling intervals on unmount
  useEffect(() => {
    return () => {
      pollIntervals.forEach(interval => clearInterval(interval));
    };
  }, [pollIntervals]);

  const getStatusIcon = () => {
    if (!ollamaStatus) return <RefreshCw className="h-4 w-4 animate-spin text-gray-400" />;
    if (!ollamaStatus.installed) return <AlertTriangle className="h-4 w-4 text-gray-400" />;
    if (!ollamaStatus.running) return <Server className="h-4 w-4 text-gray-400" />;
    return <CheckCircle className="h-4 w-4 text-gray-300" />;
  };

  const getStatusText = () => {
    if (!ollamaStatus) return "Checking...";
    if (!ollamaStatus.installed) return "Not Installed";
    if (!ollamaStatus.running) return "Not Running";
    return "Running";
  };

  const getStatusColor = (): "secondary" | "destructive" | "outline" | "warning" | "success" | null | undefined => {
    return "secondary";
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Create a unified list of all models (downloaded first, then available for download)
  const allModels: ModelWithStatus[] = [];
  
  // Add downloaded models first (sorted alphabetically)
  if (ollamaStatus?.available_models) {
    const sortedDownloaded = [...ollamaStatus.available_models].sort();
    sortedDownloaded.forEach(modelName => {
      // Try to find the model in recommended list for display name
      const recommendedModel = recommendedModels.find(m => m.model_name === modelName);
      allModels.push({
        model_name: modelName,
        display_name: recommendedModel?.display_name || modelName,
        provider: 'Ollama',
        isDownloaded: true
      });
    });
  }
  
  // Add non-downloaded recommended models (sorted alphabetically by display name)
  // Exclude models that are already downloaded OR currently being downloaded
  const nonDownloadedModels = recommendedModels
    .filter(model => 
      !ollamaStatus?.available_models?.includes(model.model_name) && 
      !activeDownloads.has(model.model_name)
    )
    .sort((a, b) => a.display_name.localeCompare(b.display_name))
    .map(model => ({
      ...model,
      isDownloaded: false
    }));
  
  allModels.push(...nonDownloadedModels);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-100 dark:text-gray-100 mb-2">Ollama</h2>
          <p className="text-sm text-gray-400 dark:text-gray-400">
            Manage local AI models with Ollama for enhanced privacy and performance.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={getStatusColor()} className="flex items-center gap-1">
            {getStatusIcon()}
            {getStatusText()}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={refreshStatus}
            disabled={loading}
            className="border-gray-600/40 bg-gray-600/10 text-gray-300 hover:bg-gray-600/20 hover:border-gray-600/60 hover:text-gray-200"
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-600/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-red-400 mt-0.5" />
            <div>
              <h4 className="font-medium text-red-300">Error</h4>
              <p className="text-sm text-red-400 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {!ollamaStatus?.installed && (
        <div className="bg-gray-700/20 border border-gray-600/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-gray-400 mt-0.5" />
            <div>
              <h4 className="font-medium text-gray-300">Ollama Not Installed</h4>
              <p className="text-sm text-gray-400 mt-1">
                Install Ollama to use local AI models. Visit{' '}
                <a 
                  href="https://ollama.com" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="underline hover:no-underline text-gray-300"
                >
                  ollama.com
                </a>{' '}
                to download and install.
              </p>
            </div>
          </div>
        </div>
      )}

      {ollamaStatus?.installed && !ollamaStatus.running && (
        <div className="flex items-center justify-between bg-gray-700/20 border border-gray-600/30 rounded-lg p-4">
          <div>
            <h4 className="font-medium text-gray-300">Start Ollama Server</h4>
            <p className="text-sm text-gray-400">
              Ollama is installed but not currently running.
            </p>
          </div>
          <Button
            onClick={startOllamaServer}
            disabled={actionLoading === 'start-server'}
            className="flex items-center gap-2 bg-green-600/20 border-green-600/40 text-primary hover:bg-green-600/30 hover:border-green-600/60 hover:text-primary"
          >
            <Play className="h-4 w-4" />
            {actionLoading === 'start-server' ? 'Starting...' : 'Start Server'}
          </Button>
        </div>
      )}

      {ollamaStatus?.running && (
        <div className="flex items-center justify-between bg-gray-700/20 border border-gray-600/30 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-gray-300" />
            <div>
              <span className="font-medium text-gray-200">
                Ollama Server Running
              </span>
              <p className="text-sm text-gray-400">
                Server available at {ollamaStatus.server_url}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            onClick={stopOllamaServer}
            disabled={actionLoading === 'stop-server'}
            className="flex items-center gap-2 border-gray-600/40 bg-gray-600/10 text-gray-300 hover:bg-gray-600/20 hover:border-gray-600/60 hover:text-gray-200"
          >
            <Square className="h-4 w-4" />
            {actionLoading === 'stop-server' ? 'Stopping...' : 'Disconnect'}
          </Button>
        </div>
      )}

      {ollamaStatus?.running && (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-gray-100">Available Models</h3>
            <span className="text-xs text-gray-400">
              {ollamaStatus.available_models.length} downloaded
            </span>
          </div>
          
          {/* Show active downloads */}
          {Object.entries(downloadProgress).map(([modelName, progress]) => (
            <div key={`download-${modelName}`} className="bg-gray-700/30 rounded-md px-3 py-3 border border-gray-600/40">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm text-gray-200">
                    {recommendedModels.find(m => m.model_name === modelName)?.display_name || modelName}
                  </span>
                  <Badge className={cn(
                    "text-xs border",
                    progress.status === 'downloading' && "bg-blue-600/30 text-primary border-blue-600/40",
                    progress.status === 'completed' && "bg-green-600/30 text-green-300 border-green-600/40",
                    progress.status === 'error' && "bg-red-600/30 text-red-300 border-red-600/40",
                    progress.status === 'cancelled' && "bg-gray-600/30 text-gray-300 border-gray-600/40"
                  )}>
                    {progress.status === 'downloading' && 'Downloading'}
                    {progress.status === 'completed' && 'Completed'}
                    {progress.status === 'error' && 'Failed'}
                    {progress.status === 'cancelled' && 'Cancelled'}
                    {!['downloading', 'completed', 'error', 'cancelled'].includes(progress.status) && progress.status}
                  </Badge>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => cancelDownload(modelName)}
                  disabled={cancellingDownloads.has(modelName) || ['completed', 'error', 'cancelled'].includes(progress.status)}
                  className="text-gray-400 hover:text-gray-300 h-6 w-6 p-0"
                >
                  {cancellingDownloads.has(modelName) ? (
                    <RefreshCw className="h-3 w-3 animate-spin" />
                  ) : (
                    <X className="h-3 w-3" />
                  )}
                </Button>
              </div>
              
              {/* Progress bar */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>{progress.phase || progress.status}</span>
                  <span>{progress.percentage ? `${progress.percentage.toFixed(1)}%` : '...'}</span>
                </div>
                <div className="w-full bg-gray-600/30 rounded-full h-2">
                  <div 
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress.percentage || 0}%` }}
                  />
                </div>
                {progress.bytes_downloaded && progress.total_bytes && (
                  <div className="text-xs text-gray-400">
                    {formatBytes(progress.bytes_downloaded)} / {formatBytes(progress.total_bytes)}
                  </div>
                )}
                {progress.message && (
                  <div className="text-xs text-gray-400 truncate">{progress.message}</div>
                )}
              </div>
            </div>
          ))}
          
          {allModels.length > 0 ? (
            <div className="space-y-1">
              {allModels.map((model) => (
                <div 
                  key={model.model_name} 
                  className="group flex items-center justify-between bg-gray-700/30 hover:bg-gray-700/50 rounded-md px-3 py-2.5 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm truncate text-gray-200">{model.display_name}</span>
                      {model.model_name !== model.display_name && (
                        <span className="font-mono text-xs text-gray-400">
                          {model.model_name}
                        </span>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    {model.isDownloaded && (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setDeleteConfirmation({
                              isOpen: true,
                              modelName: model.model_name,
                              displayName: model.display_name
                            });
                          }}
                          disabled={actionLoading === `delete-${model.model_name}`}
                          className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-gray-300 h-6 w-6 p-0"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                        <Badge className="text-xs bg-gray-600/30 text-gray-300 border-gray-600/40">
                          <CheckCircle className="h-3 w-3 mr-1" />
                          Downloaded
                        </Badge>
                      </>
                    )}
                    {!model.isDownloaded && !activeDownloads.has(model.model_name) && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => downloadModelWithProgress(model.model_name)}
                        className="flex items-center gap-2 h-7 bg-blue-600/20 border-blue-600/40 text-primary hover:bg-blue-600/30 hover:border-blue-600/60 hover:text-primary"
                      >
                        <Download className="h-3 w-3" />
                        Download
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400">
              <Brain className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No models available</p>
            </div>
          )}
        </div>
      )}
      
      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirmation.isOpen} onOpenChange={(open) => {
        if (!open) cancelDeleteModel();
      }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-400" />
              Delete Model
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete <strong>{deleteConfirmation.displayName}</strong>?
              <br />
              <span className="text-sm text-gray-400 mt-1 block">
                Model: {deleteConfirmation.modelName}
              </span>
              <br />
              This action cannot be undone. You will need to download the model again to use it.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2">
            <Button
              variant="outline"
              onClick={cancelDeleteModel}
              disabled={actionLoading === `delete-${deleteConfirmation.modelName}`}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDeleteModel}
              disabled={actionLoading === `delete-${deleteConfirmation.modelName}`}
              className="flex items-center gap-2"
            >
              <Trash2 className="h-4 w-4" />
              {actionLoading === `delete-${deleteConfirmation.modelName}` ? 'Deleting...' : 'Delete Model'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}