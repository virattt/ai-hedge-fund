import ComponentItem from '@/components/sidebar/component-item';
import { AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { useFlowContext } from '@/contexts/flow-context';
import { ComponentGroup } from '@/data/sidebar-components';

interface ComponentItemGroupProps {
  group: ComponentGroup;
  activeItem: string | null;
}

export function ComponentItemGroup({ 
  group, 
  activeItem
}: ComponentItemGroupProps) {
  const { name, icon: Icon, iconColor, items } = group;
  const { addComponentToFlow } = useFlowContext();

  const handleItemClick = async (componentName: string) => {
    try {
      await addComponentToFlow(componentName);
    } catch (error) {
      console.error('Failed to add component to flow:', error);
    }
  };
  
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
          {items.map((item) => (
            <ComponentItem 
              key={item.name}
              icon={item.icon} 
              label={item.name} 
              isActive={activeItem === item.name}
              onClick={() => handleItemClick(item.name)}
            />
          ))}
        </div>
      </AccordionContent>
    </AccordionItem>
  );
} 