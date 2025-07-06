import { Card, CardContent } from '@/components/ui/card';

export function AppearanceSettings() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-100 dark:text-gray-100 mb-2">Appearance</h2>
        <p className="text-sm text-gray-400 dark:text-gray-400">
          Customize the look and feel of your application.
        </p>
      </div>
      <Card className="bg-panel border-gray-700 dark:border-gray-700">
        <CardContent className="p-6">
          <div className="text-sm text-gray-400 dark:text-gray-400">
            Theme and appearance settings will be implemented here.
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 