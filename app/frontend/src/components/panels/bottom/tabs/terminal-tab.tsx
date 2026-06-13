import { useI18n } from '@/i18n/use-i18n';

interface TerminalTabProps {
  className?: string;
}

export function TerminalTab({ className }: TerminalTabProps) {
  const { t } = useI18n();

  return (
    <div className={className}>
      <div className="h-full rounded-md p-3 font-mono text-sm text-green-500 overflow-auto">
        <div className="whitespace-pre-wrap">
          <span className="text-blue-500">$ </span>
          <span className="text-primary">{t('bottom.terminalWelcome')}</span>
          {'\n'}
          <span className="text-muted-foreground">{t('bottom.terminalPlaceholder')}</span>
          {'\n'}
          <span className="text-blue-500">$ </span>
          <span className="animate-pulse">_</span>
        </div>
      </div>
    </div>
  );
}
