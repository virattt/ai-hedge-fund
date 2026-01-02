import {
  BadgeDollarSign,
  Bot,
  Brain,
  Calculator,
  ChartLine,
  ChartPie,
  LucideIcon,
  Network,
  Play,
  Zap
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
      name: "Start Nodes",
      icon: Play,
      iconColor: "text-blue-500",
      items: [
        { name: "Portfolio Input", icon: ChartPie },
        { name: "Stock Input", icon: ChartLine },
      ]
    },
    {
      name: "Analysts",
      icon: Bot,
      iconColor: "text-red-500",
      items: agents.map((agent: Agent) => ({
        name: agent.display_name,
        icon: Bot
      }))
    },
    {
      name: "Swarms",
      icon: Network,
      iconColor: "text-yellow-500",
      items: [
        { name: "Data Wizards", icon: Calculator },
        { name: "Market Mavericks", icon: Zap },
        { name: "Value Investors", icon: BadgeDollarSign },
      ]
    },
    {
      name: "End Nodes",
      icon: Brain,
      iconColor: "text-green-500",
      items: [
        { name: "Portfolio Manager", icon: Brain },
        // { name: "JSON Output", icon: FileJson },
        // { name: "Investment Report", icon: FileText },
      ]
    },
  ];
};