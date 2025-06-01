import {
  ArrowDownToLine,
  ArrowUpFromLine,
  BadgeDollarSign,
  Bot,
  FileJson,
  LucideIcon,
  Type,
  Users
} from 'lucide-react';
import { agents } from './agents';

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

// Define all component groups and items
export const componentGroups: ComponentGroup[] = [
  {
    name: "agents",
    icon: Bot,
    iconColor: "text-red-400",
    items: agents.map(agent => ({
      name: agent.display_name,
      icon: Bot
    }))
  },
  {
    name: "inputs",
    icon: ArrowDownToLine,
    iconColor: "text-blue-400",
    items: [
      // { name: "Chat Input", icon: MessageSquare },
      { name: "Text Input", icon: Type },
      // { name: "File Input", icon: FileText }
    ]
  },
  {
    name: "outputs",
    icon: ArrowUpFromLine,
    iconColor: "text-green-400",
    items: [
      { name: "JSON Output", icon: FileJson },
      { name: "Text Output", icon: Type },
    ]
  },
  {
    name: "swarms",
    icon: Users,
    iconColor: "text-yellow-400",
    items: [
      { name: "Value Investors", icon: BadgeDollarSign },
    ]
  }
]; 