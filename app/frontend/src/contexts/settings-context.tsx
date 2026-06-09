import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from 'react';
import { LanguageModel, getModels } from '@/data/models';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8765';

interface SettingsContextValue {
  selectedModel: LanguageModel | null;
  models: LanguageModel[];
  setSelectedModel: (model: LanguageModel) => void;
  loading: boolean;
}

const SettingsContext = createContext<SettingsContextValue>({
  selectedModel: null,
  models: [],
  setSelectedModel: () => {},
  loading: true,
});

export function useSettings() {
  return useContext(SettingsContext);
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [models, setModels] = useState<LanguageModel[]>([]);
  const [selectedModel, setSelectedModelState] = useState<LanguageModel | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [fetchedModels, savedSetting] = await Promise.all([
          getModels(),
          fetch(`${API_BASE_URL}/settings/llm`).then((r) => r.json()),
        ]);
        setModels(fetchedModels);

        const match = fetchedModels.find((m) => m.model_name === savedSetting.model_name);
        setSelectedModelState(match || fetchedModels[0] || null);
      } catch {
        try {
          const fetchedModels = await getModels();
          setModels(fetchedModels);
          setSelectedModelState(fetchedModels[0] || null);
        } catch {
          // models endpoint also failed
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const setSelectedModel = useCallback(
    (model: LanguageModel) => {
      setSelectedModelState(model);
      fetch(`${API_BASE_URL}/settings/llm`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: model.model_name, model_provider: model.provider }),
      }).catch(() => {});
    },
    [],
  );

  return (
    <SettingsContext.Provider value={{ selectedModel, models, setSelectedModel, loading }}>
      {children}
    </SettingsContext.Provider>
  );
}
