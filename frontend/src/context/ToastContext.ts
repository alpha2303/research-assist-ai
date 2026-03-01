import { createContext } from 'react';
import type { AddToastOptions } from '../components/Toast';

export interface ToastContextValue {
  addToast: (options: AddToastOptions) => void;
  removeToast: (id: number) => void;
}

export const ToastContext = createContext<ToastContextValue | undefined>(undefined);
