import { NodeStatus, useNodeContext } from '@/contexts/node-context';
import { extractBaseAgentKey } from '@/data/node-mappings';
import { flowConnectionManager } from '@/hooks/use-flow-connection';
import {
  BacktestDayResult,
  BacktestPerformanceMetrics,
  BacktestRequest
} from '@/services/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const backtestApi = {
  /**
   * Runs a backtest simulation with the given parameters and streams the results
   * @param params The backtest request parameters
   * @param nodeContext Node context for updating node states
   * @param flowId The ID of the current flow
   * @returns A function to abort the SSE connection
   */
  runBacktest: (
    params: BacktestRequest,
    nodeContext: ReturnType<typeof useNodeContext>,
    flowId: string | null = null
  ): (() => void) => {
    // Create the controller for aborting the request
    const controller = new AbortController();
    const { signal } = controller;

    // Make a POST request to the backtest endpoint
    fetch(`${API_BASE_URL}/hedge-fund/backtest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(params),
      signal,
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
            
      // Process the response as a stream of SSE events
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Failed to get response reader');
      }
      
      const decoder = new TextDecoder();
      let buffer = '';
      
      // Local array to accumulate backtest results
      let backtestResults: any[] = [];
      
      // Function to process the stream
      const processStream = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
              break;
            }
            
            // Decode the chunk and add to buffer
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            
            // Process any complete events in the buffer (separated by double newlines)
            const events = buffer.split('\n\n');
            buffer = events.pop() || '';
            
            for (const eventText of events) {
              if (!eventText.trim()) continue;
                            
              try {
                // Parse the event type and data from the SSE format
                const eventTypeMatch = eventText.match(/^event: (.+)$/m);
                const dataMatch = eventText.match(/^data: (.+)$/m);
                
                if (eventTypeMatch && dataMatch) {
                  const eventType = eventTypeMatch[1];
                  const eventData = JSON.parse(dataMatch[1]);
                  
                  console.log(`Parsed backtest ${eventType} event:`, eventData);
                  
                  // Process based on event type
                  switch (eventType) {
                    case 'start':
                      // Reset all nodes at the start of a new backtest
                      nodeContext.resetAllNodes(flowId);
                      // Clear local backtest results
                      backtestResults = [];
                      // Create a backtest agent entry
                      nodeContext.updateAgentNode(flowId, 'backtest', {
                        status: 'IN_PROGRESS',
                        message: 'Starting backtest...',
                        backtestResults: [],
                      });
                      break;
                    
                    case 'progress':
                      // Handle individual agent updates (from actual agents during backtest)
                      if (eventData.agent && eventData.agent !== 'backtest') {
                        // Map the progress to a node status
                        let nodeStatus: NodeStatus = 'IN_PROGRESS';
                        if (eventData.status === 'Done') {
                          nodeStatus = 'COMPLETE';
                        }
                        // Map the backend agent name to the unique node ID
                        const baseAgentKey = eventData.agent.replace('_agent', '');
                        
                        // Find the unique node ID that corresponds to this base agent key
                        // We need to get the agent IDs from the request parameters
                        const agentIds = params.graph_nodes.map(node => node.id);
                        const uniqueNodeId = agentIds.find(id => 
                          extractBaseAgentKey(id) === baseAgentKey
                        ) || baseAgentKey;
                                                
                        // Use the enhanced API to update both status and additional data
                        nodeContext.updateAgentNode(flowId, uniqueNodeId, {
                          status: nodeStatus,
                          ticker: eventData.ticker,
                          message: eventData.status,
                          analysis: eventData.analysis,
                          timestamp: eventData.timestamp
                        });
                      }
                      // Handle backtest-specific progress updates
                      else if (eventData.agent === 'backtest') {
                        // If this progress update contains backtest result data, add it to local array
                        if (eventData.analysis) {
                          try {
                            const backtestResultData = JSON.parse(eventData.analysis);
                            // Add to local array and keep only the last 50 results to avoid memory issues
                            backtestResults = [...backtestResults, backtestResultData].slice(-50);
                          } catch (error) {
                            console.error('Error parsing backtest result data:', error);
                          }
                        }
                        
                        // Update the node with the local backtest results
                        nodeContext.updateAgentNode(flowId, 'backtest', {
                          status: 'IN_PROGRESS',
                          message: eventData.status,
                          backtestResults: backtestResults,
                        });
                      }
                      break;
                    
                    case 'complete':
                      // Store the complete backtest results
                      if (eventData.data) {
                        const backtestResults = {
                          decisions: { backtest: { type: 'backtest_complete' } },
                          analyst_signals: {},
                          performance_metrics: eventData.data.performance_metrics,
                          final_portfolio: eventData.data.final_portfolio,
                          total_days: eventData.data.total_days,
                        };
                        
                        nodeContext.setOutputNodeData(flowId, backtestResults);
                      }
                      
                      // Mark the backtest agent as complete
                      nodeContext.updateAgentNode(flowId, 'backtest', {
                        status: 'COMPLETE',
                        message: 'Backtest completed successfully',
                      });
                      
                      // Update the output node
                      nodeContext.updateAgentNode(flowId, 'output', {
                        status: 'COMPLETE',
                        message: 'Backtest analysis complete'
                      });

                      // Update flow connection state to completed
                      if (flowId) {
                        flowConnectionManager.setConnection(flowId, {
                          state: 'completed',
                          abortController: null,
                        });

                        // Auto-cleanup completed connections after a delay
                        setTimeout(() => {
                          const currentConnection = flowConnectionManager.getConnection(flowId);
                          if (currentConnection.state === 'completed') {
                            flowConnectionManager.setConnection(flowId, {
                              state: 'idle',
                            });
                          }
                        }, 30000); // 30 seconds
                      }
                      break;
                    
                    case 'error':
                      // Mark nodes as error when there's an error
                      nodeContext.updateAgentNode(flowId, 'portfolio-start', {
                        status: 'ERROR',
                        message: eventData.message || 'Backtest failed',
                      });
                      
                      // Update flow connection state to error
                      if (flowId) {
                        flowConnectionManager.setConnection(flowId, {
                          state: 'error',
                          error: eventData.message || 'Unknown error occurred',
                          abortController: null,
                        });
                      }
                      break;
                    
                    default:
                      console.warn('Unknown backtest event type:', eventType);
                  }
                }
              } catch (err) {
                console.error('Error parsing backtest SSE event:', err, 'Raw event:', eventText);
              }
            }
          }
          
          // After the stream has finished, check if we are still in a connected state
          if (flowId) {
            const currentConnection = flowConnectionManager.getConnection(flowId);
            if (currentConnection.state === 'connected') {
              flowConnectionManager.setConnection(flowId, {
                state: 'completed',
                abortController: null,
              });
            }
          }
        } catch (error: any) {
          if (error.name === 'AbortError') {
          } else {
            console.error('Error reading backtest SSE stream:', error);
            // Mark nodes as error when there's a connection error
            nodeContext.updateAgentNode(flowId, 'portfolio-start', {
              status: 'ERROR',
              message: 'Connection error during backtest',
            });
            
            // Update flow connection state to error
            if (flowId) {
              flowConnectionManager.setConnection(flowId, {
                state: 'error',
                error: error.message || 'Connection error',
                abortController: null,
              });
            }
          }
        }
      };
      
      // Start processing the stream
      processStream();
    })
    .catch((error: any) => {
      console.error('Backtest SSE connection error:', error);
      // Mark nodes as error when there's a connection error
      nodeContext.updateAgentNode(flowId, 'portfolio-start', {
        status: 'ERROR',
        message: 'Failed to connect to backtest service',
      });
      
      // Update flow connection state to error
      if (flowId) {
        flowConnectionManager.setConnection(flowId, {
          state: 'error',
          error: error.message || 'Connection failed',
          abortController: null,
        });
      }
    });

    // Return abort function
    return () => {
      controller.abort();
      // Update connection state when manually aborted
      if (flowId) {
        flowConnectionManager.setConnection(flowId, {
          state: 'idle',
          abortController: null,
        });
      }
    };
  },
};

export type { BacktestDayResult, BacktestPerformanceMetrics, BacktestRequest };
