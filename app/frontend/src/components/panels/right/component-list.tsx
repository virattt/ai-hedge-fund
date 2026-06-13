import { Accordion } from '@/components/ui/accordion';
import { ComponentGroup } from '@/data/sidebar-components';
import { useI18n } from '@/i18n/use-i18n';
import { SearchBox } from '../search-box';
import { ComponentItemGroup } from './component-item-group';

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
  const { t } = useI18n();

  return (
    <div className="flex-grow overflow-auto text-primary scrollbar-thin scrollbar-thumb-ramp-grey-700">
      <SearchBox
        value={searchQuery}
        onChange={onSearchChange}
        placeholder={t('components.searchPlaceholder')}
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <div className="text-muted-foreground text-sm">{t('components.loading')}</div>
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
        <div className="text-center py-8 text-muted-foreground text-sm">
          {componentGroups.length === 0 ? (
            <div className="space-y-2">
              <div>{t('components.noneAvailable')}</div>
              <div className="text-xs">{t('components.loadedHere')}</div>
            </div>
          ) : (
            t('components.noneMatch')
          )}
        </div>
      )}
    </div>
  );
}
