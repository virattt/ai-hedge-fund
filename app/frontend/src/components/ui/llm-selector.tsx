import { Check, ChevronsUpDown } from "lucide-react"
import * as React from "react"

import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { type LanguageModel } from "@/data/models"
import { cn } from "@/lib/utils"

interface ModelSelectorProps {
  models: LanguageModel[];
  value: string;
  onChange: (item: LanguageModel | null) => void;
  placeholder?: string;
}

export function ModelSelector({ 
  models, 
  value, 
  onChange, 
  placeholder = "Select a model..." 
}: ModelSelectorProps) {
  const [open, setOpen] = React.useState(false)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
        >
          <span className="text-subtitle">
            {value
              ? models.find((model) => model.model_name === value)?.display_name
              : placeholder}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-full min-w-[300px] p-0">
        <Command>
          <CommandInput placeholder="Search model..." className="h-9" />
          <CommandList>
            <CommandEmpty>No model found.</CommandEmpty>
            <CommandGroup>
              {models.map((model) => (
                <CommandItem
                  key={model.model_name}
                  value={model.model_name}
                  onSelect={(currentValue) => {
                    if (currentValue === value) {
                      onChange(null);
                    } else {
                      const selectedModel = models.find(m => m.model_name === currentValue);
                      if (selectedModel) {
                        onChange(selectedModel);
                      }
                    }
                    setOpen(false);
                  }}
                >
                  <div className="flex flex-col items-start">
                    <span className="text-title">{model.display_name}</span>
                    <span className="text-subtitle text-muted-foreground">{model.provider}</span>
                  </div>
                  <Check
                    className={cn(
                      "ml-auto",
                      value === model.model_name ? "opacity-100" : "opacity-0"
                    )}
                  />
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
} 