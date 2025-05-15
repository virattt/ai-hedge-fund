import { AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { ComponentGroup, ComponentItem } from '@/data/sidebar-components';
import { SidebarItem } from './sidebar-item';

interface ComponentGroupProps {
  group: ComponentGroup;
  activeItem: string | null;
  onItemClick: (itemName: string) => void;
  onComponentAdd?: (componentName: string) => void;
}

export function ComponentGroupItem({ 
  group, 
  activeItem, 
  onItemClick,
  onComponentAdd
}: ComponentGroupProps) {
  const { name, icon: Icon, iconColor, items } = group;
  
  return (
    <AccordionItem key={name} value={name} className="border-none">
      <AccordionTrigger className="px-4 py-2 text-sm hover:bg-ramp-grey-700 hover:no-underline">
        <div className="flex items-center gap-2">
          <Icon size={16} className={iconColor} />
          <span className="capitalize">{name}</span>
        </div>
      </AccordionTrigger>
      <AccordionContent className="px-4">
        <div className="space-y-1">
          {items.map((item: ComponentItem) => (
            <SidebarItem 
              key={item.name}
              icon={item.icon} 
              label={item.name} 
              isActive={activeItem === item.name}
              onClick={() => onItemClick(item.name)}
              onAddClick={onComponentAdd ? () => onComponentAdd(item.name) : undefined}
            />
          ))}
        </div>
      </AccordionContent>
    </AccordionItem>
  );
} 