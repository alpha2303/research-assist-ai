/**
 * Global keyboard shortcuts hook.
 *
 * Shortcuts:
 *   Ctrl+N / Cmd+N  →  Create new chat (dispatches 'app:new-chat' CustomEvent)
 *   Escape          →  Close mobile drawer (dispatches 'app:escape' CustomEvent)
 */

import { useEffect } from 'react';

export function useKeyboardShortcuts() {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ctrl/Cmd + N → new chat
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent('app:new-chat'));
      }

      // Escape → generic escape (for drawer close, etc.)
      if (e.key === 'Escape') {
        window.dispatchEvent(new CustomEvent('app:escape'));
      }
    };

    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);
}
