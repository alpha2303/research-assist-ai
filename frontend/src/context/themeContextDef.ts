/**
 * ThemeContext definition — separated from ThemeProvider to satisfy
 * react-refresh/only-export-components.
 */

import { createContext } from 'react';

export type Theme = 'light' | 'dark';

export interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextType | undefined>(undefined);
