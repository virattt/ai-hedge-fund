
interface ComponentActionsProps {
  onToggleCollapse: () => void;
}

export function ComponentActions({ onToggleCollapse }: ComponentActionsProps) {
  return (
    <div className="p-2 flex justify-between flex-shrink-0 items-center border-b border-ramp-grey-700 mt-4">
      <span className="text-white text-sm font-medium ml-4">Components</span>
      {/* <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggleCollapse}
          className="h-6 w-6 text-white hover:bg-ramp-grey-700"
          aria-label="Toggle sidebar"
          title={`Toggle Components Panel (${formatKeyboardShortcut('B')})`}
        >
          <PanelRight size={16} />
        </Button>
      </div> */}
    </div>
  );
} 