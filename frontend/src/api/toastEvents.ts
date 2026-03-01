/**
 * Lightweight event bus so non-React code (e.g. the Axios interceptor)
 * can push toast notifications into the React tree.
 *
 * Usage (producer — outside React):
 *   import { emitToast } from './toastEvents';
 *   emitToast({ type: 'error', message: 'Network error' });
 *
 * Usage (consumer — inside ToastProvider):
 *   import { onToast, offToast } from './toastEvents';
 *   useEffect(() => { const unsub = onToast(handler); return unsub; }, []);
 */

import type { AddToastOptions } from '../components/Toast';

type Listener = (options: AddToastOptions) => void;

const listeners = new Set<Listener>();

/** Subscribe to toast events. Returns an unsubscribe function. */
export function onToast(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Unsubscribe a listener. */
export function offToast(fn: Listener): void {
  listeners.delete(fn);
}

/** Emit a toast event from anywhere in the app (including non-React code). */
export function emitToast(options: AddToastOptions): void {
  listeners.forEach((fn) => fn(options));
}
