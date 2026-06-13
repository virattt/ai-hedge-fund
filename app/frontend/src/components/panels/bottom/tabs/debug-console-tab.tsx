import { useI18n } from '@/i18n/use-i18n';

interface DebugConsoleTabProps {
  className?: string;
}

export function DebugConsoleTab({ className }: DebugConsoleTabProps) {
  const { t } = useI18n();

  return (
    <div className={className}>
      <div className="h-full bg-background/50 rounded-md p-3 text-sm overflow-auto">
        <div className="text-muted-foreground">
          {t('bottom.debugReady')}
        </div>
      </div>
    </div>
  );
}
