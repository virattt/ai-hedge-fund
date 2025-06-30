import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Platform detection utility
export function isMac(): boolean {
  return typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;
}

// Keyboard shortcut formatting utility
export function formatKeyboardShortcut(key: string): string {
  const modifierKey = isMac() ? '⌘' : 'Ctrl';
  return `${modifierKey}${key.toUpperCase()}`;
}
