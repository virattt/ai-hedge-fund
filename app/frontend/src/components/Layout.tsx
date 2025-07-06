import { BottomPanel } from '@/components/panels/bottom/bottom-panel';
import { LeftSidebar } from '@/components/panels/left/left-sidebar';
import { RightSidebar } from '@/components/panels/right/right-sidebar';
import { TabBar } from '@/components/tabs/tab-bar';
import { TabContent } from '@/components/tabs/tab-content';
import { SidebarProvider } from '@/components/ui/sidebar';
import { FlowProvider, useFlowContext } from '@/contexts/flow-context';
import { TabsProvider, useTabsContext } from '@/contexts/tabs-context';
import { useLayoutKeyboardShortcuts } from '@/hooks/use-keyboard-shortcuts';
import { cn } from '@/lib/utils';
import { SidebarStorageService } from '@/services/sidebar-storage';
import { TabService } from '@/services/tab-service';
import { ReactFlowProvider } from '@xyflow/react';
import { ReactNode, useEffect, useState } from 'react';
import { TopBar } from './layout/top-bar';

// Create a LayoutContent component to access the FlowContext and TabsContext
function LayoutContent({ children }: { children: ReactNode }) {
  const { reactFlowInstance } = useFlowContext();
  const { openTab } = useTabsContext();
  
  // Initialize sidebar states from storage service
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(() => 
    SidebarStorageService.loadLeftSidebarState(true)
  );
  
  const [isRightCollapsed, setIsRightCollapsed] = useState(() => 
    SidebarStorageService.loadRightSidebarState(true)
  );

  const [isBottomCollapsed, setIsBottomCollapsed] = useState(() => 
    SidebarStorageService.loadBottomPanelState(true)
  );

  // Track actual sidebar widths for dynamic positioning
  const [leftSidebarWidth, setLeftSidebarWidth] = useState(280);
  const [rightSidebarWidth, setRightSidebarWidth] = useState(280);
  const [bottomPanelHeight, setBottomPanelHeight] = useState(300);

  const handleSettingsClick = () => {
    const tabData = TabService.createSettingsTab();
    openTab(tabData);
  };

  // Add keyboard shortcuts for toggling sidebars and fit view
  useLayoutKeyboardShortcuts(
    () => setIsRightCollapsed(!isRightCollapsed), // Cmd+I for right sidebar
    () => setIsLeftCollapsed(!isLeftCollapsed),   // Cmd+B for left sidebar
    () => reactFlowInstance.fitView({ padding: 0.1, duration: 500 }), // Cmd+O for fit view
    // Note: undo/redo will be handled directly in the Flow component for now
    undefined, // undo
    undefined, // redo
    () => setIsBottomCollapsed(!isBottomCollapsed), // Cmd+J for bottom panel
    handleSettingsClick, // Shift+Cmd+J for settings
  );

  // Save sidebar states whenever they change
  useEffect(() => {
    SidebarStorageService.saveLeftSidebarState(isLeftCollapsed);
  }, [isLeftCollapsed]);

  useEffect(() => {
    SidebarStorageService.saveRightSidebarState(isRightCollapsed);
  }, [isRightCollapsed]);

  useEffect(() => {
    SidebarStorageService.saveBottomPanelState(isBottomCollapsed);
  }, [isBottomCollapsed]);

  // Calculate tab bar and bottom panel positioning based on actual sidebar widths
  const getSidebarBasedStyle = () => {
    let left = 0;
    let right = 0;
    
    if (!isLeftCollapsed) {
      left = leftSidebarWidth;
    }
    
    if (!isRightCollapsed) {
      right = rightSidebarWidth;
    }
    
    return {
      left: `${left}px`,
      right: `${right}px`,
    };
  };

  // Calculate main content positioning accounting for tab bar height
  const getMainContentStyle = () => {
    const tabBarHeight = 40; // Approximate tab bar height
    let top = tabBarHeight;
    let bottom = 0;
    
    if (!isBottomCollapsed) {
      bottom = bottomPanelHeight;
    }
    
    return {
      top: `${top}px`,
      bottom: `${bottom}px`,
      left: '0',
      right: '0',
      width: 'auto',
      height: 'auto',
    };
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden relative bg-background">
      {/* VSCode-style Top Bar */}
      <TopBar
        isLeftCollapsed={isLeftCollapsed}
        isRightCollapsed={isRightCollapsed}
        isBottomCollapsed={isBottomCollapsed}
        onToggleLeft={() => setIsLeftCollapsed(!isLeftCollapsed)}
        onToggleRight={() => setIsRightCollapsed(!isRightCollapsed)}
        onToggleBottom={() => setIsBottomCollapsed(!isBottomCollapsed)}
        onSettingsClick={handleSettingsClick}
      />

      {/* Tab Bar - positioned absolutely like bottom panel */}
      <div 
        className="absolute top-0 z-10 transition-all duration-200"
        style={getSidebarBasedStyle()}
      >
        <TabBar />
      </div>

      {/* Main content area */}
      <main 
        className="absolute inset-0 overflow-hidden" 
        style={{
          left: !isLeftCollapsed ? `${leftSidebarWidth}px` : '0px',
          right: !isRightCollapsed ? `${rightSidebarWidth}px` : '0px',
          top: '40px', // Tab bar height
          bottom: !isBottomCollapsed ? `${bottomPanelHeight}px` : '0px',
        }}
      >
        <TabContent className="h-full w-full" />
      </main>

      {/* Floating left sidebar */}
      <div className={cn(
        "absolute top-0 left-0 z-30 h-full transition-transform",
        isLeftCollapsed && "transform -translate-x-full opacity-0"
      )}>
        <LeftSidebar
          isCollapsed={isLeftCollapsed}
          onCollapse={() => setIsLeftCollapsed(true)}
          onExpand={() => setIsLeftCollapsed(false)}
          onToggleCollapse={() => setIsLeftCollapsed(!isLeftCollapsed)}
          onWidthChange={setLeftSidebarWidth}
        />
      </div>

      {/* Floating right sidebar */}
      <div className={cn(
        "absolute top-0 right-0 z-30 h-full transition-transform",
        isRightCollapsed && "transform translate-x-full opacity-0"
      )}>
        <RightSidebar
          isCollapsed={isRightCollapsed}
          onCollapse={() => setIsRightCollapsed(true)}
          onExpand={() => setIsRightCollapsed(false)}
          onToggleCollapse={() => setIsRightCollapsed(!isRightCollapsed)}
          onWidthChange={setRightSidebarWidth}
        />
      </div>

      {/* Bottom panel */}
      <div 
        className={cn(
          "absolute bottom-0 z-20 transition-transform",
          isBottomCollapsed && "transform translate-y-full opacity-0"
        )}
        style={getSidebarBasedStyle()}
      >
        <BottomPanel
          isCollapsed={isBottomCollapsed}
          onCollapse={() => setIsBottomCollapsed(true)}
          onExpand={() => setIsBottomCollapsed(false)}
          onToggleCollapse={() => setIsBottomCollapsed(!isBottomCollapsed)}
          onHeightChange={setBottomPanelHeight}
        />
      </div>
    </div>
  );
}

type LayoutProps = {
  children?: ReactNode;
};

export function Layout({ children }: LayoutProps) {
  return (
    <SidebarProvider defaultOpen={true}>
      <ReactFlowProvider>
        <FlowProvider>
          <TabsProvider>
            <LayoutContent>{children}</LayoutContent>
          </TabsProvider>
        </FlowProvider>
      </ReactFlowProvider>
    </SidebarProvider>
  );
}