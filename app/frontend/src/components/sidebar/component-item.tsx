import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { LucideIcon, Plus } from "lucide-react";
import { useState } from "react";

interface ComponentItemProps {
  icon: LucideIcon;
  label: string;
  onClick?: () => void;
  className?: string;
  isActive?: boolean;
}

export default function ComponentItem({ 
  icon: Icon, 
  label, 
  onClick, 
  className, 
  isActive = false 
}: ComponentItemProps) {
  const [isHovered, setIsHovered] = useState(false);
  
  const handlePlusClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent triggering the parent onClick
    if (onClick) onClick();
  };
  
  return (
    <div 
      className={cn(
        "group flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors duration-150",
        isActive ? "bg-ramp-grey-700 text-white" : "text-gray-300",
        isHovered ? "bg-ramp-grey-700" : "",
        className
      )}
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && onClick) {
          onClick();
        }
      }}
    >
      <div className="flex-shrink-0">
        <Icon size={16} className={isActive ? "text-white" : "text-gray-400"} />
      </div>
      <span className="truncate">{label}</span>
      
      {/* Add button using shadcn Button */}
      <div className="ml-auto opacity-0 group-hover:opacity-100">
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5 p-0 hover:bg-transparent hover:text-white text-gray-500"
          onClick={handlePlusClick}
          aria-label="Add"
        >
          <Plus size={14} />
        </Button>
      </div>
    </div>
  );
} 