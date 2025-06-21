export interface FlowState {
  nodes: any[];
  edges: any[];
  viewport: {
    x: number;
    y: number;
    zoom: number;
  };
}

export class FlowStorageService {
  private static readonly FLOW_KEY = 'ai-hedge-fund-flow';

  /**
   * Save flow state to localStorage
   */
  static saveFlow(flowState: FlowState): boolean {
    try {
      const serializedFlow = JSON.stringify(flowState);
      localStorage.setItem(this.FLOW_KEY, serializedFlow);
      return true;
    } catch (error) {
      console.error('Failed to save flow to localStorage:', error);
      return false;
    }
  }

  /**
   * Load flow state from localStorage
   */
  static loadFlow(): FlowState | null {
    try {
      const serializedFlow = localStorage.getItem(this.FLOW_KEY);
      
      if (!serializedFlow) {
        return null;
      }

      const flowState = JSON.parse(serializedFlow);
      
      // Validate the structure
      if (this.isValidFlowState(flowState)) {
        return flowState;
      }
      
      console.warn('Invalid flow state structure found in localStorage');
      return null;
    } catch (error) {
      console.error('Failed to load flow from localStorage:', error);
      return null;
    }
  }

  /**
   * Clear saved flow from localStorage
   */
  static clearFlow(): boolean {
    try {
      localStorage.removeItem(this.FLOW_KEY);
      return true;
    } catch (error) {
      console.error('Failed to clear flow from localStorage:', error);
      return false;
    }
  }

  /**
   * Check if flow exists in localStorage
   */
  static hasFlow(): boolean {
    try {
      return localStorage.getItem(this.FLOW_KEY) !== null;
    } catch (error) {
      console.error('Failed to check flow existence in localStorage:', error);
      return false;
    }
  }

  /**
   * Get the size of stored flow data in bytes
   */
  static getFlowSize(): number {
    try {
      const serializedFlow = localStorage.getItem(this.FLOW_KEY);
      return serializedFlow ? new Blob([serializedFlow]).size : 0;
    } catch (error) {
      console.error('Failed to get flow size:', error);
      return 0;
    }
  }

  /**
   * Validate flow state structure
   */
  private static isValidFlowState(flowState: any): flowState is FlowState {
    return (
      flowState &&
      typeof flowState === 'object' &&
      Array.isArray(flowState.nodes) &&
      Array.isArray(flowState.edges) &&
      flowState.viewport &&
      typeof flowState.viewport.x === 'number' &&
      typeof flowState.viewport.y === 'number' &&
      typeof flowState.viewport.zoom === 'number'
    );
  }
} 