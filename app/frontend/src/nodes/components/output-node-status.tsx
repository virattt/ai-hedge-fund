import { cn } from '@/lib/utils';
import { getStatusColor } from '../utils';

interface OutputNodeStatusProps {
  isProcessing: boolean;
  isAnyAgentRunning: boolean;
  isOutputAvailable: boolean;
  isConnected: boolean;
  onViewOutput?: () => void;
  processingText?: string;
  completingText?: string;
  availableText?: string;
  idleText?: string;
}

export function OutputNodeStatus({
  isProcessing,
  isAnyAgentRunning,
  isOutputAvailable,
  isConnected,
  onViewOutput,
  processingText = "In Progress",
  completingText = "Completing",
  availableText = "View Output",
  idleText = "Idle"
}: OutputNodeStatusProps) {
  // Determine the current state and appropriate styling
  const isLocallyProcessing = isProcessing; // Connected agents are running
  const isGloballyProcessing = !isProcessing && isAnyAgentRunning; // Other agents running
  const hasGradientAnimation = isLocallyProcessing || isGloballyProcessing;
  const isClickable = isOutputAvailable && !isLocallyProcessing && !isGloballyProcessing;
  
  // Determine display text based on current state
  let displayText: string;
  if (isLocallyProcessing) {
    displayText = processingText; // "In Progress"
  } else if (isGloballyProcessing) {
    displayText = completingText; // "Completing"
  } else if (isOutputAvailable) {
    displayText = availableText; // "View Output"
  } else {
    displayText = idleText; // "Idle"
  }

  const status = hasGradientAnimation ? 'IN_PROGRESS' : 'IDLE';

  return (
    <div 
      className={cn(
        "text-foreground text-xs rounded p-2 border border-border transition-colors",
        hasGradientAnimation ? "gradient-animation" : getStatusColor(status),
        isClickable && "bg-primary text-primary-foreground cursor-pointer hover:bg-primary/80",
        !isOutputAvailable && !hasGradientAnimation && "opacity-50"
      )}
      onClick={isClickable ? onViewOutput : undefined}
    >
      {hasGradientAnimation ? (
        <div className="flex items-center gap-2 justify-center">
          <span className="capitalize">{displayText}</span>
        </div>
      ) : (
        <span className="capitalize">{displayText}</span>
      )}
    </div>
  );
} 