import { api } from '@/services/api';

export interface Agent {
  key: string;
  display_name: string;
  description: string;
  order: number;
}

// In-memory cache for agents to avoid repeated API calls
let agents: Agent[] | null = null;

/**
 * Get the list of agents from the backend API
 * Uses caching to avoid repeated API calls
 */
export const getAgents = async (): Promise<Agent[]> => {
  if (agents) {
    return agents;
  }
  
  try {
    agents = await api.getAgents();
    return agents;
  } catch (error) {
    console.error('Failed to fetch agents:', error);
    throw error; // Let the calling component handle the error
  }
};
