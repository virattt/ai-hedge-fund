import { useI18n } from '@/i18n/use-i18n';

interface ProblemsTabProps {
  className?: string;
}

export function ProblemsTab({ className }: ProblemsTabProps) {
  const { t } = useI18n();

  return (
    <div className={className}>
      <div className="h-full bg-background/50 rounded-md p-3 text-sm overflow-auto">
        <div className="text-muted-foreground">
          {t('bottom.noProblems')}
        </div>
      </div>
    </div>
  );
}
