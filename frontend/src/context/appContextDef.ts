/**
 * Shared context definition for the application state.
 *
 * Kept in its own module so that AppContext.tsx can export only components
 * (satisfying react-refresh/only-export-components).
 */

import { createContext } from 'react';
import type { AppState, AppAction } from '../types';

export interface AppContextValue {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

export const AppContext = createContext<AppContextValue | undefined>(undefined);
