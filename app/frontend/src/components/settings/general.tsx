import { Card, CardContent } from '@/components/ui/card';

export function GeneralSettings() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-100 dark:text-gray-100 mb-2">General</h2>
        <p className="text-sm text-gray-400 dark:text-gray-400">
          General application settings and preferences.
        </p>
      </div>
      <Card className="bg-panel border-gray-700 dark:border-gray-700">
        <CardContent className="p-6">
          <div className="text-sm text-gray-400 dark:text-gray-400">
            General settings will be implemented here.
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 