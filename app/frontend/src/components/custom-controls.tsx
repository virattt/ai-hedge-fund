import { ResetIcon } from '@radix-ui/react-icons';
import { ControlButton, Controls } from '@xyflow/react';

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
            <ControlButton onClick={onReset} title="Reset Flow">
              <ResetIcon />
            </ControlButton>
    </Controls>
  );
} 