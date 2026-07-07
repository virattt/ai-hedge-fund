import { ChevronsUpDown } from "lucide-react"
import * as React from "react"

import { Badge } from "@/components/ui/badge"
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
import { useConfiguredProviders } from "@/hooks/use-configured-providers"
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
  const { providers } = useConfiguredProviders()

  // A model is enabled if its provider has a key configured on the backend. While the
  // provider list is still loading (null), don't gray anything out.
  const isEnabled = React.useCallback(
    (model: LanguageModel) => providers === null || providers.includes(model.provider),
    [providers]
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between bg-node border border-border"
        >
          <span className="text-subtitle">
            {value
              ? models.find((model) => model.model_name === value)?.display_name
              : placeholder}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-full min-w-[350px] p-0 bg-node border border-border shadow-lg">
        <Command className="bg-node">
          <CommandInput placeholder="Search model..." className="h-9 bg-node" />
          <CommandList className="bg-node">
            <CommandEmpty>No model found.</CommandEmpty>
            <CommandGroup>
              {models.map((model) => {
                const enabled = isEnabled(model);
                return (
                <CommandItem
                  key={model.model_name}
                  value={model.model_name}
                  disabled={!enabled}
                  title={enabled ? undefined : `No API key configured for ${model.provider}`}
                  className={cn(
                    "bg-node",
                    enabled
                      ? "cursor-pointer hover:bg-accent"
                      : "opacity-40 cursor-not-allowed data-[disabled=true]:opacity-40",
                    value === model.model_name && "bg-blue-600/10 border-l-2 border-blue-500/50"
                  )}
                  onSelect={(currentValue) => {
                    if (!enabled) {
                      return;
                    }
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
                  <div className="flex items-center justify-between w-full">
                    <div className="flex flex-col items-start min-w-0 flex-1">
                      <span className="text-title">{model.display_name}</span>
                      <span className="text-xs text-muted-foreground font-mono">{model.model_name}</span>
                    </div>
                    <Badge className="text-xs text-primary bg-primary/10 border-primary/30 hover:bg-primary/20 hover:border-primary/50">
                      {model.provider}
                    </Badge>
                  </div>
                </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
} 