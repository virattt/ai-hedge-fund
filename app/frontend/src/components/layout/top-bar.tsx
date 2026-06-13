import { Button } from '@/components/ui/button';
import { useI18n } from '@/i18n/use-i18n';
import { cn } from '@/lib/utils';
import { Languages, PanelBottom, PanelLeft, PanelRight, Settings } from 'lucide-react';

interface TopBarProps {
  isLeftCollapsed: boolean;
  isRightCollapsed: boolean;
  isBottomCollapsed: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onToggleBottom: () => void;
  onSettingsClick: () => void;
}

export function TopBar({
  isLeftCollapsed,
  isRightCollapsed,
  isBottomCollapsed,
  onToggleLeft,
  onToggleRight,
  onToggleBottom,
  onSettingsClick,
}: TopBarProps) {
  const { locale, t, toggleLocale } = useI18n();
  const currentLanguage = locale === 'zh-CN' ? t('language.chinese') : t('language.english');
  const languageTitle = locale === 'zh-CN'
    ? t('language.switchToEnglish')
    : t('language.switchToChinese');

  return (
    <div className="absolute top-0 right-0 z-40 flex items-center gap-0 py-1 px-2 bg-panel/80">
      {/* Left Sidebar Toggle */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggleLeft}
        className={cn(
          "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
          !isLeftCollapsed && "text-foreground"
        )}
        aria-label={t('topBar.toggleLeftSidebar')}
        title={`${t('topBar.toggleLeftSidebar')} (⌘B)`}
      >
        <PanelLeft size={16} />
      </Button>

      {/* Bottom Panel Toggle */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggleBottom}
        className={cn(
          "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
          !isBottomCollapsed && "text-foreground"
        )}
        aria-label={t('topBar.toggleBottomPanel')}
        title={`${t('topBar.toggleBottomPanel')} (⌘J)`}
      >
        <PanelBottom size={16} />
      </Button>

      {/* Right Sidebar Toggle */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggleRight}
        className={cn(
          "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
          !isRightCollapsed && "text-foreground"
        )}
        aria-label={t('topBar.toggleRightSidebar')}
        title={`${t('topBar.toggleRightSidebar')} (⌘I)`}
      >
        <PanelRight size={16} />
      </Button>

      {/* Divider */}
      <div className="w-px h-5 bg-ramp-grey-700 mx-1" />

      {/* Language */}
      <Button
        variant="ghost"
        size="sm"
        onClick={toggleLocale}
        className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
        aria-label={languageTitle}
        title={`${languageTitle} (${t('language.current', { language: currentLanguage })})`}
      >
        <Languages size={16} />
      </Button>

      {/* Settings */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onSettingsClick}
        className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
        aria-label={t('topBar.openSettings')}
        title={`${t('topBar.openSettings')} (⌘,)`}
      >
        <Settings size={16} />
      </Button>
    </div>
  );
}
