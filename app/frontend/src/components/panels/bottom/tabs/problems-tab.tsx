interface ProblemsTabProps {
  className?: string;
}

export function ProblemsTab({ className }: ProblemsTabProps) {
  return (
    <div className={className}>
      <div className="h-full bg-background/50 rounded-md p-3 text-sm overflow-auto">
        <div className="text-muted-foreground">
          No problems detected
        </div>
      </div>
    </div>
  );
} 