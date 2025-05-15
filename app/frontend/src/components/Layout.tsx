import { SidebarProvider } from '@/components/ui/sidebar';
import { FlowProvider } from '@/contexts/flow-context';
import { cn } from '@/lib/utils';
import { ReactFlowProvider } from '@xyflow/react';
import { PanelLeft } from 'lucide-react';
import { ReactNode, useState } from 'react';
import { LeftSidebar } from './sidebar/left-sidebar';
import { Button } from './ui/button';

type LayoutProps = {
  leftSidebar?: ReactNode;
  rightSidebar?: ReactNode;
  children: ReactNode;
};

export function Layout({ leftSidebar, rightSidebar, children }: LayoutProps) {
  const [isCollapsed, setIsCollapsed] = useState(true);

  return (
    <SidebarProvider defaultOpen={!isCollapsed}>
      <div className="flex h-screen w-screen overflow-hidden relative bg-background">
        <ReactFlowProvider>
          <FlowProvider>
            {/* Main content area takes full width */}
            <main className="flex-1 h-full overflow-hidden w-full">
              {children}
            </main>

            {/* Floating left sidebar */}
            <div className={cn(
              "absolute top-0 left-0 z-30 h-full transition-transform",
              isCollapsed && "transform -translate-x-full opacity-0"
            )}>
              <LeftSidebar
                isCollapsed={isCollapsed}
                onCollapse={() => setIsCollapsed(true)}
                onExpand={() => setIsCollapsed(false)}
                onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
              >
                {leftSidebar}
              </LeftSidebar>
            </div>

            {/* Sidebar toggle button - visible when sidebar is collapsed */}
            {isCollapsed && (
              <Button 
                className="absolute top-4 left-4 z-30 bg-ramp-grey-800 text-white p-2 rounded-md hover:bg-ramp-grey-700"
                onClick={() => setIsCollapsed(false)}
                aria-label="Show sidebar"
              >
                Components <PanelLeft size={16} />
              </Button>
            )}

            {/* Right sidebar */}
            {rightSidebar && (
              <div className="h-full w-64 bg-gray-900 border-l border-gray-800 ml-auto flex-shrink-0">
                {rightSidebar}
              </div>
            )}
          </FlowProvider>
        </ReactFlowProvider>
      </div>
    </SidebarProvider>
  );
}