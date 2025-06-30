import { Flow } from '@/types/flow';
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from 'react';

// Define tab types
export type TabType = 'flow' | 'settings';

export interface Tab {
  id: string;
  type: TabType;
  title: string;
  content: ReactNode;
  // For flow tabs
  flow?: Flow;
  // For other tabs (settings, etc.)
  metadata?: Record<string, any>;
}

// Serializable version of Tab for localStorage (without content)
interface SerializableTab {
  id: string;
  type: TabType;
  title: string;
  flow?: Flow;
  metadata?: Record<string, any>;
}

interface TabsContextType {
  tabs: Tab[];
  activeTabId: string | null;
  openTab: (tab: Omit<Tab, 'id'> & { id?: string }) => void;
  closeTab: (tabId: string) => void;
  setActiveTab: (tabId: string) => void;
  closeAllTabs: () => void;
  isTabOpen: (identifier: string, type: TabType) => boolean;
  getTabByIdentifier: (identifier: string, type: TabType) => Tab | undefined;
  reorderTabs: (fromIndex: number, toIndex: number) => void;
  updateTabTitle: (tabId: string, newTitle: string) => void;
  updateFlowTabTitle: (flowId: number, newTitle: string) => void;
}

const TabsContext = createContext<TabsContextType | null>(null);

export function useTabsContext() {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error('useTabsContext must be used within a TabsProvider');
  }
  return context;
}

interface TabsProviderProps {
  children: ReactNode;
}

// localStorage keys
const TABS_STORAGE_KEY = 'ai-hedge-fund-tabs';
const ACTIVE_TAB_STORAGE_KEY = 'ai-hedge-fund-active-tab';

export function TabsProvider({ children }: TabsProviderProps) {
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Generate unique tab ID
  const generateTabId = useCallback((type: TabType, identifier?: string): string => {
    if (type === 'flow' && identifier) {
      return `flow-${identifier}`;
    }
    if (type === 'settings') {
      return 'settings';
    }
    return `${type}-${Date.now()}`;
  }, []);

  // Save tabs to localStorage
  const saveTabsToStorage = useCallback((tabsToSave: Tab[], activeId: string | null) => {
    try {
      // Convert tabs to serializable format (without content)
      const serializableTabs: SerializableTab[] = tabsToSave.map(tab => ({
        id: tab.id,
        type: tab.type,
        title: tab.title,
        flow: tab.flow,
        metadata: tab.metadata,
      }));
      
      localStorage.setItem(TABS_STORAGE_KEY, JSON.stringify(serializableTabs));
      localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, activeId || '');
    } catch (error) {
      console.error('Failed to save tabs to localStorage:', error);
    }
  }, []);

  // Load tabs from localStorage
  const loadTabsFromStorage = useCallback((): { tabs: SerializableTab[], activeTabId: string | null } => {
    try {
      const savedTabs = localStorage.getItem(TABS_STORAGE_KEY);
      const savedActiveTabId = localStorage.getItem(ACTIVE_TAB_STORAGE_KEY);
      
      if (savedTabs) {
        const parsedTabs: SerializableTab[] = JSON.parse(savedTabs);
        return {
          tabs: parsedTabs,
          activeTabId: savedActiveTabId || null,
        };
      }
    } catch (error) {
      console.error('Failed to load tabs from localStorage:', error);
    }
    
    return { tabs: [], activeTabId: null };
  }, []);

  // Initialize tabs from localStorage on mount
  useEffect(() => {
    if (!isInitialized) {
      const { tabs: savedTabs, activeTabId: savedActiveTabId } = loadTabsFromStorage();
      
      if (savedTabs.length > 0) {
        // We'll restore the content later when the tab service is available
        // For now, just set up the tab structure
        const restoredTabs: Tab[] = savedTabs.map(savedTab => ({
          ...savedTab,
          content: null, // Will be filled in by TabService when tabs are accessed
        }));
        
        setTabs(restoredTabs);
        setActiveTabId(savedActiveTabId);
      }
      
      setIsInitialized(true);
    }
  }, [isInitialized, loadTabsFromStorage]);

  // Save tabs to localStorage whenever they change
  useEffect(() => {
    if (isInitialized) {
      saveTabsToStorage(tabs, activeTabId);
    }
  }, [tabs, activeTabId, isInitialized, saveTabsToStorage]);

  // Check if a tab is already open
  const isTabOpen = useCallback((identifier: string, type: TabType): boolean => {
    const tabId = generateTabId(type, identifier);
    return tabs.some(tab => tab.id === tabId);
  }, [tabs, generateTabId]);

  // Get tab by identifier
  const getTabByIdentifier = useCallback((identifier: string, type: TabType): Tab | undefined => {
    const tabId = generateTabId(type, identifier);
    return tabs.find(tab => tab.id === tabId);
  }, [tabs, generateTabId]);

  // Open a new tab or focus existing one
  const openTab = useCallback((tabData: Omit<Tab, 'id'> & { id?: string }) => {
    const tabId = tabData.id || generateTabId(tabData.type, 
      tabData.type === 'flow' && tabData.flow ? tabData.flow.id.toString() : undefined
    );

    setTabs(prevTabs => {
      // Check if tab already exists
      const existingTabIndex = prevTabs.findIndex(tab => tab.id === tabId);
      
      if (existingTabIndex !== -1) {
        // Tab exists, just update it and focus
        const updatedTabs = [...prevTabs];
        updatedTabs[existingTabIndex] = { ...tabData, id: tabId };
        setActiveTabId(tabId);
        return updatedTabs;
      } else {
        // Create new tab
        const newTab: Tab = { ...tabData, id: tabId };
        setActiveTabId(tabId);
        return [...prevTabs, newTab];
      }
    });
  }, [generateTabId]);

  // Close a tab
  const closeTab = useCallback((tabId: string) => {
    setTabs(prevTabs => {
      const newTabs = prevTabs.filter(tab => tab.id !== tabId);
      
      // If closing active tab, set new active tab
      if (activeTabId === tabId) {
        if (newTabs.length > 0) {
          // Find the index of the closed tab
          const closedIndex = prevTabs.findIndex(tab => tab.id === tabId);
          // Try to activate the tab to the right, or the last tab if closing the last one
          const newActiveIndex = closedIndex < newTabs.length ? closedIndex : newTabs.length - 1;
          setActiveTabId(newTabs[newActiveIndex]?.id || null);
        } else {
          setActiveTabId(null);
        }
      }
      
      return newTabs;
    });
  }, [activeTabId]);

  // Set active tab
  const setActiveTab = useCallback((tabId: string) => {
    if (tabs.some(tab => tab.id === tabId)) {
      setActiveTabId(tabId);
    }
  }, [tabs]);

  // Close all tabs
  const closeAllTabs = useCallback(() => {
    setTabs([]);
    setActiveTabId(null);
  }, []);

  // Reorder tabs
  const reorderTabs = useCallback((fromIndex: number, toIndex: number) => {
    setTabs(prevTabs => {
      const newTabs = [...prevTabs];
      const [movedTab] = newTabs.splice(fromIndex, 1);
      newTabs.splice(toIndex, 0, movedTab);
      return newTabs;
    });
  }, []);

  // Update tab title
  const updateTabTitle = useCallback((tabId: string, newTitle: string) => {
    setTabs(prevTabs => {
      const updatedTabs = prevTabs.map(tab =>
        tab.id === tabId ? { ...tab, title: newTitle } : tab
      );
      return updatedTabs;
    });
  }, []);

  // Update flow tab title
  const updateFlowTabTitle = useCallback((flowId: number, newTitle: string) => {
    setTabs(prevTabs => {
      const updatedTabs = prevTabs.map(tab => {
        if (tab.type === 'flow' && tab.flow?.id === flowId) {
          return { 
            ...tab, 
            title: newTitle,
            // Also update the flow object's name to keep it in sync
            flow: tab.flow ? { ...tab.flow, name: newTitle } : tab.flow
          };
        }
        return tab;
      });
      return updatedTabs;
    });
  }, []);

  const value = {
    tabs,
    activeTabId,
    openTab,
    closeTab,
    setActiveTab,
    closeAllTabs,
    isTabOpen,
    getTabByIdentifier,
    reorderTabs,
    updateTabTitle,
    updateFlowTabTitle,
  };

  return (
    <TabsContext.Provider value={value}>
      {children}
    </TabsContext.Provider>
  );
} 