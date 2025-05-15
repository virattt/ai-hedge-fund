import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { MessageItem } from '@/contexts/node-context';
import { MessageSquare } from 'lucide-react';

interface AgentOutputDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  messages: MessageItem[];
}

export function AgentOutputDialog({ 
  isOpen, 
  onOpenChange, 
  name, 
  messages 
}: AgentOutputDialogProps) {
  // Format ISO timestamp to local browser time
  const formatTime = (timestamp: string) => {
    // Parse ISO timestamp string into Date object
    const date = new Date(timestamp);
    
    // Format as HH:MM:SS in local browser timezone
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <div className="border-t border-border p-3 flex justify-end items-center cursor-pointer hover:bg-accent/50" onClick={() => onOpenChange(true)}>
          <div className="flex items-center gap-1">
            <div className="text-subtitle text-muted-foreground">Messages</div>
            <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
        </div>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{name} Activity Log</DialogTitle>
        </DialogHeader>
        <div className="py-4 max-h-[400px] overflow-y-auto">
          {messages.length > 0 ? (
            <div className="space-y-3">
              {messages.map((msg, idx) => (
                <div key={idx} className="border-l-2 border-primary pl-3 text-sm">
                  <div className="text-blue-500">
                    {formatTime(msg.timestamp)}
                  </div>
                  <div className="text-foreground">
                  {msg.ticker && <span className="ml-1">[{msg.ticker}] </span>}
                  {msg.message}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-6">
              No activity yet
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
} 