interface TerminalTabProps {
  className?: string;
}

export function TerminalTab({ className }: TerminalTabProps) {
  return (
    <div className={className}>
      <div className="h-full rounded-md p-3 font-mono text-sm text-green-500 overflow-auto">
        <div className="whitespace-pre-wrap">
          <span className="text-blue-500">$ </span>
          <span className="text-primary">Welcome to AI Hedge Fund Terminal</span>
          {'\n'}
          <span className="text-muted-foreground">Type commands here...</span>
          {'\n'}
          <span className="text-blue-500">$ </span>
          <span className="animate-pulse">_</span>
        </div>
      </div>
    </div>
  );
} 