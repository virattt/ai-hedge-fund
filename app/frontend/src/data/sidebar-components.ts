import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Bot,
  LucideIcon,
  Type
} from 'lucide-react';

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
        { name: "Text Output", icon: Type },
      ]
    },
  // {
  //   name: "data",
  //   icon: Database,
  //   iconColor: "text-yellow-400",
  //   items: [
  //     { name: "Data Store", icon: Database },
  //     { name: "Vector Store", icon: LinkIcon }
  //   ]
  // },
  // {
  //   name: "processing",
  //   icon: Zap,
  //   iconColor: "text-purple-400",
  //   items: [
  //     { name: "Code Processor", icon: Code },
  //     { name: "Function", icon: Zap }
  //   ]
  // },
  {
    name: "agents",
    icon: Bot,
    iconColor: "text-red-400",
    items: [
      { name: "Ben Graham", icon: Bot },
      { name: "Charlie Munger", icon: Bot },
      { name: "Warren Buffett", icon: Bot }
    ]
  }
]; 