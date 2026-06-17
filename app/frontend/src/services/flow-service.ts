import { Flow } from '@/types/flow';
import { API_ROUTES } from '@/services/api-routes';

export interface CreateFlowRequest {
  name: string;
  description?: string;
  nodes: any;
  edges: any;
  viewport?: any;
  data?: any;
  is_template?: boolean;
  tags?: string[];
}

export interface UpdateFlowRequest {
  name?: string;
  description?: string;
  nodes?: any;
  edges?: any;
  viewport?: any;
  data?: any;
  is_template?: boolean;
  tags?: string[];
}

export const flowService = {
  async getFlows(): Promise<Flow[]> {
    const response = await fetch(API_ROUTES.flows.list);
    if (!response.ok) {
      throw new Error('Failed to fetch flows');
    }
    return response.json();
  },

  async getFlow(id: number): Promise<Flow> {
    const response = await fetch(API_ROUTES.flows.detail(String(id)));
    if (!response.ok) {
      throw new Error('Failed to fetch flow');
    }
    return response.json();
  },

  async createFlow(data: CreateFlowRequest): Promise<Flow> {
    const response = await fetch(API_ROUTES.flows.list, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error('Failed to create flow');
    }
    return response.json();
  },

  async updateFlow(id: number, data: UpdateFlowRequest): Promise<Flow> {
    const response = await fetch(API_ROUTES.flows.detail(String(id)), {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error('Failed to update flow');
    }
    return response.json();
  },

  async deleteFlow(id: number): Promise<void> {
    const response = await fetch(API_ROUTES.flows.detail(String(id)), {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete flow');
    }
  },

  async duplicateFlow(id: number, newName?: string): Promise<Flow> {
    const response = await fetch(API_ROUTES.flows.duplicate(String(id), newName), {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to duplicate flow');
    }
    return response.json();
  },

  // Create a default flow for new users
  async createDefaultFlow(nodes: any, edges: any, viewport?: any): Promise<Flow> {
    return this.createFlow({
      name: 'My First Flow',
      description: 'Welcome to AI Hedge Fund! Start building your flow here.',
      nodes,
      edges,
      viewport,
    });
  },
}; 