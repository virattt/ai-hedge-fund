import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useI18n } from '@/i18n/use-i18n';
import { cn } from '@/lib/utils';
import { Languages, Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';

export function ThemeSettings() {
  const { theme, setTheme } = useTheme();
  const { locale, setLocale, t } = useI18n();

  const themes = [
    {
      id: 'light',
      name: t('appearance.light'),
      description: t('appearance.lightDescription'),
      icon: Sun,
    },
    {
      id: 'dark',
      name: t('appearance.dark'),
      description: t('appearance.darkDescription'),
      icon: Moon,
    },
    {
      id: 'system',
      name: t('appearance.system'),
      description: t('appearance.systemDescription'),
      icon: Monitor,
    },
  ];

  const languages = [
    { id: 'en' as const, name: t('language.english') },
    { id: 'zh-CN' as const, name: t('language.chinese') },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-primary mb-2">{t('appearance.title')}</h2>
        <p className="text-sm text-muted-foreground">
          {t('appearance.description')}
        </p>
      </div>

      <Card className="bg-panel border-gray-700 dark:border-gray-700">
        <CardHeader>
          <CardTitle className="text-lg font-medium text-primary">
            {t('appearance.themeCardTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {t('appearance.themeCardDescription')}
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {themes.map((themeOption) => {
              const Icon = themeOption.icon;
              const isSelected = theme === themeOption.id;

              return (
                <Button
                  key={themeOption.id}
                  variant="outline"
                  className={cn(
                    "flex flex-col items-center gap-3 h-auto p-4 bg-panel border-gray-600 hover:border-primary hover-bg",
                    isSelected && "border-blue-500 bg-blue-500/10 text-blue-500"
                  )}
                  onClick={() => setTheme(themeOption.id)}
                >
                  <Icon className="h-6 w-6" />
                  <div className="text-center">
                    <div className="font-medium text-sm">{themeOption.name}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {themeOption.description}
                    </div>
                  </div>
                </Button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-panel border-gray-700 dark:border-gray-700">
        <CardHeader>
          <CardTitle className="text-lg font-medium text-primary">
            {t('appearance.languageCardTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {t('language.description')}
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {languages.map((language) => {
              const isSelected = locale === language.id;

              return (
                <Button
                  key={language.id}
                  variant="outline"
                  className={cn(
                    "flex items-center justify-center gap-3 h-auto p-4 bg-panel border-gray-600 hover:border-primary hover-bg",
                    isSelected && "border-blue-500 bg-blue-500/10 text-blue-500"
                  )}
                  onClick={() => setLocale(language.id)}
                >
                  <Languages className="h-5 w-5" />
                  <span className="font-medium text-sm">{language.name}</span>
                </Button>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
