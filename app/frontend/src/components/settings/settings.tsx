import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface SettingsProps {
  className?: string;
}

export function Settings({ className }: SettingsProps) {
  return (
    <div className={cn("p-6 max-w-4xl mx-auto space-y-6 overflow-auto", className)}>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground">
          Configure your AI Hedge Fund application preferences.
        </p>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>General</CardTitle>
            <CardDescription>
              General application settings and preferences.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Settings configuration will be implemented here.
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Flow Settings</CardTitle>
            <CardDescription>
              Configure default behavior for flows and nodes.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Flow-specific settings will be implemented here.
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>API Configuration</CardTitle>
            <CardDescription>
              Configure API endpoints and authentication.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-sm text-muted-foreground">
              API settings will be implemented here.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 