import { useCallback, useState } from 'react';
import { toast } from 'sonner';

type ToastType = 'success' | 'error' | 'info' | 'warning';
type ToastPosition = 'top-left' | 'top-center' | 'top-right' | 'bottom-left' | 'bottom-center' | 'bottom-right';

interface ToastOptions {
  duration?: number;
  position?: ToastPosition;
  preventDuplicates?: boolean;
}

interface ToastState {
  [key: string]: boolean;
}

/**
 * A generalized toast manager hook that handles duplicate prevention and provides
 * convenience methods for different toast types.
 * 
 * @example
 * ```typescript
 * const { success, error, info, warning } = useToastManager();
 * 
 * // Basic usage
 * success('Data saved!');
 * error('Something went wrong');
 * 
 * // With custom ID to prevent duplicates
 * success('Flow saved!', 'flow-save');
 * 
 * // With custom options
 * info('Processing...', 'process', { 
 *   duration: 5000, 
 *   position: 'top-center' 
 * });
 * 
 * // Disable duplicate prevention
 * warning('Warning!', undefined, { preventDuplicates: false });
 * ```
 */
export function useToastManager() {
  const [visibleToasts, setVisibleToasts] = useState<ToastState>({});

  const showToast = useCallback((
    type: ToastType,
    message: string,
    toastId?: string,
    options: ToastOptions = {}
  ) => {
    const {
      duration = 2000,
      position = 'top-center',
      preventDuplicates = true
    } = options;

    // Use message as ID if no toastId provided
    const id = toastId || message;

    // Check if we should prevent duplicates
    if (preventDuplicates && visibleToasts[id]) {
      return;
    }

    // Mark toast as visible
    if (preventDuplicates) {
      setVisibleToasts(prev => ({ ...prev, [id]: true }));
    }

    const onDismiss = () => {
      if (preventDuplicates) {
        setVisibleToasts(prev => ({ ...prev, [id]: false }));
      }
    };

    const onAutoClose = () => {
      if (preventDuplicates) {
        setVisibleToasts(prev => ({ ...prev, [id]: false }));
      }
    };

    // Show the appropriate toast type
    switch (type) {
      case 'success':
        toast.success(message, {
          duration,
          position,
          onDismiss,
          onAutoClose,
        });
        break;
      case 'error':
        toast.error(message, {
          duration,
          position,
          onDismiss,
          onAutoClose,
        });
        break;
      case 'info':
        toast.info(message, {
          duration,
          position,
          onDismiss,
          onAutoClose,
        });
        break;
      case 'warning':
        toast.warning(message, {
          duration,
          position,
          onDismiss,
          onAutoClose,
        });
        break;
    }
  }, [visibleToasts]);

  // Convenience methods for specific toast types
  const success = useCallback((message: string, toastId?: string, options?: ToastOptions) => {
    showToast('success', message, toastId, options);
  }, [showToast]);

  const error = useCallback((message: string, toastId?: string, options?: ToastOptions) => {
    showToast('error', message, toastId, options);
  }, [showToast]);

  const info = useCallback((message: string, toastId?: string, options?: ToastOptions) => {
    showToast('info', message, toastId, options);
  }, [showToast]);

  const warning = useCallback((message: string, toastId?: string, options?: ToastOptions) => {
    showToast('warning', message, toastId, options);
  }, [showToast]);

  return {
    showToast,
    success,
    error,
    info,
    warning,
    visibleToasts,
  };
} 