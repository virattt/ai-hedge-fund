import { Accordion } from '@/components/ui/accordion';
import { ComponentGroup } from '@/data/sidebar-components';
import { ComponentItemGroup } from './right/component-item-group';
import { SearchBox } from './search-box';

interface ComponentListProps {
  componentGroups: ComponentGroup[];
  searchQuery: string;
  isLoading: boolean;
  openGroups: string[];
  filteredGroups: ComponentGroup[];
  activeItem: string | null;
  onSearchChange: (query: string) => void;
  onAccordionChange: (value: string[]) => void;
}

export function ComponentList({
  componentGroups,
  searchQuery,
  isLoading,
  openGroups,
  filteredGroups,
  activeItem,
  onSearchChange,
  onAccordionChange,
}: ComponentListProps) {
  return (
    <div className="flex-grow overflow-auto text-white scrollbar-thin scrollbar-thumb-ramp-grey-700">
      <SearchBox 
        value={searchQuery} 
        onChange={onSearchChange}
        placeholder="Search components..."
      />
      
      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-400 text-sm">Loading components...</div>
        </div>
      ) : (
        <Accordion 
          type="multiple" 
          className="w-full" 
          value={openGroups} 
          onValueChange={onAccordionChange}
        >
          {filteredGroups.map(group => (
            <ComponentItemGroup
              key={group.name} 
              group={group}
              activeItem={activeItem}
            />
          ))}
        </Accordion>
      )}

      {!isLoading && filteredGroups.length === 0 && (
        <div className="text-center py-8 text-gray-400 text-sm">
          {componentGroups.length === 0 ? (
            <div className="space-y-2">
              <div>No components available</div>
              <div className="text-xs">Components will appear here when loaded</div>
            </div>
          ) : (
            'No components match your search'
          )}
        </div>
      )}
    </div>
  );
} 