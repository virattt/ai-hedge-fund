import { ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { actionKeys, displayNameKeys, signalKeys, statusKeys } from './display-names';
import { I18nContext } from './i18n-context';
import type { I18nContextValue, TranslationValues } from './i18n-context';
import { translations } from './translations';
import type { Locale, TranslationKey } from './translations';

const LANGUAGE_STORAGE_KEY = 'ai-hedge-fund-language';

const isLocale = (value: string | null): value is Locale => {
  return value === 'en' || value === 'zh-CN';
};

const interpolate = (template: string, values?: TranslationValues) => {
  if (!values) return template;

  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = values[key];
    return value === undefined || value === null ? `{${key}}` : String(value);
  });
};

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window === 'undefined') return 'en';

    const savedLocale = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (isLocale(savedLocale)) return savedLocale;

    return navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en';
  });

  const setLocale = useCallback((nextLocale: Locale) => {
    setLocaleState(nextLocale);
  }, []);

  const toggleLocale = useCallback(() => {
    setLocaleState((currentLocale) => (currentLocale === 'en' ? 'zh-CN' : 'en'));
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale === 'zh-CN' ? 'zh-CN' : 'en';
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, locale);
  }, [locale]);

  const t = useCallback((key: TranslationKey, values?: TranslationValues) => {
    const localized = translations[locale][key] ?? translations.en[key];
    return interpolate(localized, values);
  }, [locale]);

  const translateDisplayName = useCallback((value: string) => {
    const key = displayNameKeys[value];
    return key ? t(key) : value;
  }, [t]);

  const translateStatus = useCallback((value: string) => {
    const key = statusKeys[value];
    return key ? t(key) : value.toLowerCase().replace(/_/g, ' ');
  }, [t]);

  const translateAction = useCallback((value?: string | null) => {
    if (!value) return t('action.unknown');
    const key = actionKeys[value.toLowerCase()];
    return key ? t(key) : value.toUpperCase();
  }, [t]);

  const translateSignal = useCallback((value?: string | null) => {
    if (!value) return t('signal.unknown');
    const key = signalKeys[value.toLowerCase()];
    return key ? t(key) : value.toUpperCase();
  }, [t]);

  const value = useMemo<I18nContextValue>(() => ({
    locale,
    setLocale,
    toggleLocale,
    t,
    translateDisplayName,
    translateStatus,
    translateAction,
    translateSignal,
  }), [
    locale,
    setLocale,
    toggleLocale,
    t,
    translateDisplayName,
    translateStatus,
    translateAction,
    translateSignal,
  ]);

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  );
}
