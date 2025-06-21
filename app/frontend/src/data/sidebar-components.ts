import {
  BadgeDollarSign,
  Bot,
  Brain,
  Calculator,
  FileJson,
  FileText,
  LucideIcon,
  Network,
  Play,
  StopCircle
} from 'lucide-react';
import { Agent, getAgents } from './agents';

// Define component items by group
export interface ComponentItem {
  name: string;
  icon: LucideIcon;
}

export interface ComponentGroup {
  name: string;
  icon: LucideIcon;
  iconColor: string;
  items: ComponentItem[];
}

/**
 * Get all component groups, including agents fetched from the backend
 */
export const getComponentGroups = async (): Promise<ComponentGroup[]> => {
  const agents = await getAgents();
  
  return [
    {
      name: "start nodes",
      icon: Play,
      iconColor: "text-blue-400",
      items: [
        // { name: "Chat Input", icon: MessageSquare },
        { name: "Portfolio Manager", icon: Brain },
        // { name: "File Input", icon: FileText }
      ]
    },
    {
      name: "agents",
      icon: Bot,
      iconColor: "text-red-400",
      items: agents.map((agent: Agent) => ({
        name: agent.display_name,
        icon: Bot
      }))
    },
    {
      name: "swarms",
      icon: Network,
      iconColor: "text-yellow-400",
      items: [
        { name: "Data Wizards", icon: Calculator },
        { name: "Value Investors", icon: BadgeDollarSign },
      ]
    },
    {
      name: "end nodes",
      icon: StopCircle,
      iconColor: "text-green-400",
      items: [
        { name: "JSON Output", icon: FileJson },
        { name: "Investment Report", icon: FileText },
      ]
    },
  ];
};