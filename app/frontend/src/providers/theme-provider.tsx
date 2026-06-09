import { ThemeProvider as NextThemesProvider } from 'next-themes';
import { ReactNode } from 'react';

interface ThemeProviderProps {
  children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={true}
      storageKey="theme"
    >
      {children}
    </NextThemesProvider>
  );
} 