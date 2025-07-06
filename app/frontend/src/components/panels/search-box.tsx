import { Button } from '@/components/ui/button';
import { Search } from 'lucide-react';

interface SearchBoxProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function SearchBox({ 
  value, 
  onChange, 
  placeholder = "Search components..." 
}: SearchBoxProps) {
  return (
    <div className="px-2 py-2 sticky top-0 bg-panel z-10">
      <div className="flex items-center rounded-md bg-sidebar-accent px-3 py-1">
        <Search className="h-4 w-4 text-gray-400 mr-2 flex-shrink-0" />
        <input 
          type="text" 
          placeholder={placeholder} 
          className="bg-transparent text-sm focus:outline-none text-white w-full placeholder-gray-400"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        {value && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onChange('')}
            className="h-4 w-4 text-gray-400 hover:text-white"
            aria-label="Clear search"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </Button>
        )}
      </div>
    </div>
  );
} 