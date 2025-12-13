import { CheckCircle, Clock, MoreHorizontal, XCircle } from 'lucide-react';

// Helper function to detect if content is JSON
export function isJsonString(str: string): boolean {
  try {
    const parsed = JSON.parse(str);
    return typeof parsed === 'object' && parsed !== null;
  } catch {
    return false;
  }
}

// Helper function to get display name for agent
export function getDisplayName(agentName: string): string {
  // Remove _agent suffix first
  let name = agentName.replace("_agent", "");
  
  // Remove ID suffix (everything after the last underscore if it looks like an ID)
  const lastUnderscoreIndex = name.lastIndexOf("_");
  if (lastUnderscoreIndex !== -1) {
    const potentialId = name.substring(lastUnderscoreIndex + 1);
    // If the part after the last underscore looks like an ID (alphanumeric, 5+ chars), remove it
    if (/^[a-zA-Z0-9]{5,}$/.test(potentialId)) {
      name = name.substring(0, lastUnderscoreIndex);
    }
  }
  
  // Replace remaining underscores with spaces and title case
  return name.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
}

// Helper function to get status icon and color
export function getStatusIcon(status: string) {
  switch (status.toLowerCase()) {
    case 'complete':
      return { icon: CheckCircle, color: 'text-green-500' };
    case 'error':
      return { icon: XCircle, color: 'text-red-500' };
    case 'in_progress':
      return { icon: MoreHorizontal, color: 'text-yellow-500' };
    default:
      return { icon: Clock, color: 'text-muted-foreground' };
  }
}

// Helper function to get signal color
export function getSignalColor(signal: string): string {
  switch (signal.toUpperCase()) {
    case 'BULLISH':
      return 'text-green-500';
    case 'BEARISH':
      return 'text-red-500';
    case 'NEUTRAL':
      return 'text-primary';
    default:
      return 'text-muted-foreground';
  }
}

// Helper function to get action color
export function getActionColor(action: string): string {
  switch (action.toUpperCase()) {
    case 'BUY':
    case 'COVER':
      return 'text-green-500';
    case 'SELL':
    case 'SHORT':
      return 'text-red-500';
    case 'HOLD':
      return 'text-primary';
    default:
      return 'text-muted-foreground';
  }
}

// Helper function to sort agents in display order
export function sortAgents(agents: [string, any][]): [string, any][] {
  return agents.sort(([agentA, dataA], [agentB, dataB]) => {
    // First, sort by agent type priority (Risk Management and Portfolio Management at bottom)
    const getPriority = (agentName: string) => {
      if (agentName.includes("risk_management")) return 3;
      if (agentName.includes("portfolio_management")) return 4;
      return 1;
    };
    
    const priorityA = getPriority(agentA);
    const priorityB = getPriority(agentB);
    
    // If different priorities, sort by priority
    if (priorityA !== priorityB) {
      return priorityA - priorityB;
    }
    
    // If same priority, sort by timestamp (ascending - oldest first)
    const timestampA = dataA.timestamp ? new Date(dataA.timestamp).getTime() : 0;
    const timestampB = dataB.timestamp ? new Date(dataB.timestamp).getTime() : 0;
    
    if (timestampA !== timestampB) {
      return timestampA - timestampB;
    }
    
    // If no timestamp difference, sort alphabetically
    return agentA.localeCompare(agentB);
  });
} 