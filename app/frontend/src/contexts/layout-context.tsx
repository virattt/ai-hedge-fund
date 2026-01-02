import { SidebarStorageService } from '@/services/sidebar-storage';
import { createContext, ReactNode, useContext, useEffect, useState } from 'react';

interface LayoutContextType {
  isBottomCollapsed: boolean;
  expandBottomPanel: () => void;
  collapseBottomPanel: () => void;
  toggleBottomPanel: () => void;
  setBottomPanelTab: (tab: string) => void;
  currentBottomTab: string;
}

const LayoutContext = createContext<LayoutContextType | null>(null);

export function useLayoutContext() {
  const context = useContext(LayoutContext);
  if (!context) {
    throw new Error('useLayoutContext must be used within a LayoutProvider');
  }
  return context;
}

interface LayoutProviderProps {
  children: ReactNode;
}

export function LayoutProvider({ children }: LayoutProviderProps) {
  const [isBottomCollapsed, setIsBottomCollapsed] = useState(() => 
    SidebarStorageService.loadBottomPanelState(true)
  );
  const [currentBottomTab, setCurrentBottomTab] = useState('output');

  // Save bottom panel state when it changes
  useEffect(() => {
    SidebarStorageService.saveBottomPanelState(isBottomCollapsed);
  }, [isBottomCollapsed]);

  const expandBottomPanel = () => {
    setIsBottomCollapsed(false);
  };

  const collapseBottomPanel = () => {
    setIsBottomCollapsed(true);
  };

  const toggleBottomPanel = () => {
    setIsBottomCollapsed(!isBottomCollapsed);
  };

  const setBottomPanelTab = (tab: string) => {
    setCurrentBottomTab(tab);
  };

  const value = {
    isBottomCollapsed,
    expandBottomPanel,
    collapseBottomPanel,
    toggleBottomPanel,
    setBottomPanelTab,
    currentBottomTab,
  };

  return (
    <LayoutContext.Provider value={value}>
      {children}
    </LayoutContext.Provider>
  );
} 