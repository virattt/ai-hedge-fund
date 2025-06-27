interface OutputTabProps {
  className?: string;
}

export function OutputTab({ className }: OutputTabProps) {
  return (
    <div className={className}>
      <div className="h-full bg-background/50 rounded-md p-3 text-sm overflow-auto">
        <div className="text-muted-foreground">
          No output to display
        </div>
      </div>
    </div>
  );
} 