import { createContext } from 'react';
import type { Locale, TranslationKey } from './translations';

export type TranslationValues = Record<string, string | number>;

export interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  toggleLocale: () => void;
  t: (key: TranslationKey, values?: TranslationValues) => string;
  translateDisplayName: (value: string) => string;
  translateStatus: (value: string) => string;
  translateAction: (value?: string | null) => string;
  translateSignal: (value?: string | null) => string;
}

export const I18nContext = createContext<I18nContextValue | null>(null);
