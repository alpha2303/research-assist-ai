/**
 * ThemeProvider — manages light/dark mode state.
 *
 * - Persists preference to localStorage
 * - Falls back to system preference on first visit
 * - Applies/removes the `dark` class on <html> so Tailwind dark: variants activate
 */

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { ThemeContext } from './themeContextDef';
import type { Theme } from './themeContextDef';

const STORAGE_KEY = 'research-assist-theme';

function getInitialTheme(): Theme {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
  }
  return 'light';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = () => setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
