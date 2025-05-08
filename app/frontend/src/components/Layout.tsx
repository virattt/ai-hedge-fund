import { ReactNode } from 'react';

type LayoutProps = {
  leftSidebar?: ReactNode;
  rightSidebar?: ReactNode;
  children: ReactNode;
};

export function Layout({ leftSidebar, rightSidebar, children }: LayoutProps) {
  return (
    <div className="flex h-screen w-screen overflow-hidden">
      {leftSidebar && (
        <div className="h-full w-64 bg-gray-900 border-r border-gray-800">
          {leftSidebar}
        </div>
      )}
      
      <div className="flex-1 h-full">
        {children}
      </div>

      {rightSidebar && (
        <div className="h-full w-64 bg-gray-900 border-l border-gray-800">
          {rightSidebar}
        </div>
      )}
    </div>
  );
} 