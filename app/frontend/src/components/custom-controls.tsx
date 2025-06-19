import { ResetIcon } from '@radix-ui/react-icons';
import { ControlButton, Controls } from '@xyflow/react';
import { Tooltip, TooltipContent, TooltipTrigger } from './ui/tooltip';

type CustomControlsProps = {
  onReset: () => void;
};

export function CustomControls({ onReset }: CustomControlsProps) {
  return (
    <Controls 
      position="bottom-center" 
      orientation="horizontal" 
      style={{ bottom: 20, borderRadius: 20, gap: 10 }}
      className="bg-ramp-grey-800 text-white px-4 py-2 rounded-md [&_button]:border-0 [&_button]:outline-0 [&_button]:shadow-none"
    >
        <Tooltip>
          <TooltipTrigger asChild>
            <ControlButton onClick={onReset} title="Reset Flow">
              <ResetIcon />
            </ControlButton>
          </TooltipTrigger>
          <TooltipContent side="top" className="z-[9999]">
            <p>Reset Flow</p>
          </TooltipContent>
        </Tooltip>
    </Controls>
  );
} 