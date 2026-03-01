/**
 * Custom hooks for AppContext access.
 *
 * Separated from AppContext.tsx so that the context provider module only
 * exports components, satisfying react-refresh/only-export-components.
 */

import { useContext } from 'react';
import { AppContext } from './appContextDef';
import type { AppContextValue } from './appContextDef';
import { ThemeContext } from './themeContextDef';
import type { ThemeContextType } from './themeContextDef';

export function useAppContext(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return context;
}

export function useProjects() {
  const { state } = useAppContext();
  return state.projects;
}

export function useSelectedProject() {
  const { state } = useAppContext();
  return state.projects.find((p) => p.id === state.selectedProjectId) || null;
}

export function useSelectedProjectId() {
  const { state } = useAppContext();
  return state.selectedProjectId;
}

export function useChats() {
  const { state } = useAppContext();
  return state.chats;
}

export function useSelectedChat() {
  const { state } = useAppContext();
  return state.chats.find((c) => c.chat_id === state.selectedChatId) || null;
}

export function useSelectedChatId() {
  const { state } = useAppContext();
  return state.selectedChatId;
}

export function useMessages() {
  const { state } = useAppContext();
  return state.messages;
}

export function useTheme(): ThemeContextType {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
