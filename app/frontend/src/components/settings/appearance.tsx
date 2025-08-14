import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';

export function ThemeSettings() {
  const { theme, setTheme } = useTheme();

  const themes = [
    {
      id: 'light',
      name: 'Light',
      description: 'A clean, bright interface',
      icon: Sun,
    },
    {
      id: 'dark',
      name: 'Dark',
      description: 'A comfortable dark interface',
      icon: Moon,
    },
    {
      id: 'system',
      name: 'System',
      description: 'Use your system preference',
      icon: Monitor,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-primary mb-2">Theme</h2>
        <p className="text-sm text-muted-foreground">
          Customize the look and feel of your application.
        </p>
      </div>

      <Card className="bg-panel border-gray-700 dark:border-gray-700">
        <CardHeader>
          <CardTitle className="text-lg font-medium text-primary">
            Theme
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Select your preferred theme or use system setting to automatically switch between light and dark modes.
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
    </div>
  );
} 