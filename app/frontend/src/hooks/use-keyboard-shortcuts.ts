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

        // For shortcuts that should work with either Ctrl or Cmd
        const isModifierShortcut = (ctrlKey || metaKey) && (event.ctrlKey || event.metaKey);
        const matchesModifierShortcut = isModifierShortcut && isKeyMatch && isShiftMatch && isAltMatch;

        if (matchesSaveShortcut || matchesModifierShortcut || (isKeyMatch && isCtrlMatch && isMetaMatch && isShiftMatch && isAltMatch)) {
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

// Convenience hook for layout keyboard shortcuts
export function useLayoutKeyboardShortcuts(
  toggleRightSidebar: () => void, 
  toggleLeftSidebar?: () => void,
  fitView?: () => void,
  undo?: () => void,
  redo?: () => void,
  toggleBottomPanel?: () => void
) {
  const shortcuts: KeyboardShortcut[] = [
    {
      key: 'i',
      ctrlKey: true, // This will match either Ctrl+I or Cmd+I due to our logic above  
      metaKey: true,
      callback: toggleRightSidebar,
      preventDefault: true,
    },
  ];

  // Add left sidebar toggle if provided
  if (toggleLeftSidebar) {
    shortcuts.push({
      key: 'b',
      ctrlKey: true, // This will match either Ctrl+B or Cmd+B
      metaKey: true,
      callback: toggleLeftSidebar,
      preventDefault: true,
    });
  }

  // Add fit view shortcut if provided
  if (fitView) {
    shortcuts.push({
      key: '0',
      ctrlKey: true, // This will match either Ctrl+O or Cmd+O
      metaKey: true,
      callback: fitView,
      preventDefault: true,
    });
  }

  // Add undo shortcut if provided
  if (undo) {
    shortcuts.push({
      key: 'z',
      ctrlKey: true, // This will match either Ctrl+Z or Cmd+Z
      metaKey: true,
      callback: undo,
      preventDefault: true,
    });
  }

  // Add redo shortcut if provided
  if (redo) {
    shortcuts.push({
      key: 'z',
      ctrlKey: true, // This will match either Ctrl+Shift+Z or Cmd+Shift+Z
      metaKey: true,
      shiftKey: true,
      callback: redo,
      preventDefault: true,
    });
  }

  // Add bottom panel toggle shortcut if provided
  if (toggleBottomPanel) {
    shortcuts.push({
      key: 'j',
      ctrlKey: true, // This will match either Ctrl+J or Cmd+J (like VSCode)
      metaKey: true,
      callback: toggleBottomPanel,
      preventDefault: true,
    });
  }

  useKeyboardShortcuts({ shortcuts });
} 