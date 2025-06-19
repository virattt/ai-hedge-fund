import { useEffect } from 'react';

interface KeyboardShortcut {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  callback: () => void;
  preventDefault?: boolean;
}

interface UseKeyboardShortcutsProps {
  shortcuts: KeyboardShortcut[];
}

export function useKeyboardShortcuts({ shortcuts }: UseKeyboardShortcutsProps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      shortcuts.forEach(({ key, ctrlKey, metaKey, shiftKey, altKey, callback, preventDefault = true }) => {
        const isCtrlMatch = ctrlKey ? event.ctrlKey : !event.ctrlKey;
        const isMetaMatch = metaKey ? event.metaKey : !event.metaKey;
        const isShiftMatch = shiftKey ? event.shiftKey : !event.shiftKey;
        const isAltMatch = altKey ? event.altKey : !event.altKey;
        const isKeyMatch = event.key.toLowerCase() === key.toLowerCase();

        // For save shortcut, we want either Ctrl+S OR Cmd+S
        const isSaveShortcut = key.toLowerCase() === 's' && (ctrlKey || metaKey);
        const matchesSaveShortcut = isSaveShortcut && (event.ctrlKey || event.metaKey) && isKeyMatch;

        if (matchesSaveShortcut || (isKeyMatch && isCtrlMatch && isMetaMatch && isShiftMatch && isAltMatch)) {
          if (preventDefault) {
            event.preventDefault();
          }
          callback();
        }
      });
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [shortcuts]);
}

// Convenience hook specifically for common shortcuts
export function useFlowKeyboardShortcuts(saveFlow: (showToast?: boolean) => void) {
  const shortcuts: KeyboardShortcut[] = [
    {
      key: 's',
      ctrlKey: true, // This will match either Ctrl+S or Cmd+S due to our logic above
      metaKey: true,
      callback: () => saveFlow(true),
      preventDefault: true,
    },
  ];

  useKeyboardShortcuts({ shortcuts });
} 