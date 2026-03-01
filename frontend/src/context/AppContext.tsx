/**
 * Application context provider for global state management.
 *
 * Only the AppProvider component is exported here (for react-refresh).
 * The context definition lives in ./appContextDef.ts and hooks in ./hooks.ts.
 */

import { useReducer } from 'react';
import type { ReactNode } from 'react';
import type { AppState, AppAction } from '../types';
import { AppContext } from './appContextDef';

const initialState: AppState = {
  projects: [],
  selectedProjectId: null,
  selectedChatId: null,
  chats: [],
  messages: [],
  documents: [],
  isLoading: false,
  error: null,
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_PROJECTS':
      return { ...state, projects: action.payload, error: null };
    
    case 'ADD_PROJECT':
      return {
        ...state,
        projects: [action.payload, ...state.projects],
        error: null,
      };
    
    case 'UPDATE_PROJECT':
      return {
        ...state,
        projects: state.projects.map((p) =>
          p.id === action.payload.id ? action.payload : p
        ),
        error: null,
      };
    
    case 'DELETE_PROJECT':
      return {
        ...state,
        projects: state.projects.filter((p) => p.id !== action.payload),
        selectedProjectId:
          state.selectedProjectId === action.payload
            ? null
            : state.selectedProjectId,
        error: null,
      };
    
    case 'SELECT_PROJECT':
      return { ...state, selectedProjectId: action.payload };
    
    case 'SELECT_CHAT':
      return { ...state, selectedChatId: action.payload };
    
    case 'SET_CHATS':
      return { ...state, chats: action.payload, error: null };
    
    case 'ADD_CHAT':
      return {
        ...state,
        chats: [action.payload, ...state.chats],
        error: null,
      };
    
    case 'UPDATE_CHAT':
      return {
        ...state,
        chats: state.chats.map((c) =>
          c.chat_id === action.payload.chat_id ? action.payload : c
        ),
        error: null,
      };
    
    case 'DELETE_CHAT':
      return {
        ...state,
        chats: state.chats.filter((c) => c.chat_id !== action.payload),
        selectedChatId:
          state.selectedChatId === action.payload
            ? null
            : state.selectedChatId,
        error: null,
      };
    
    case 'SET_MESSAGES':
      return { ...state, messages: action.payload, error: null };
    
    case 'ADD_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.payload],
        error: null,
      };
    
    case 'SET_DOCUMENTS':
      return { ...state, documents: action.payload, error: null };
    
    case 'ADD_DOCUMENT':
      return {
        ...state,
        documents: [action.payload, ...state.documents],
        error: null,
      };
    
    case 'UPDATE_DOCUMENT':
      return {
        ...state,
        documents: state.documents.map((d) =>
          d.id === action.payload.id ? action.payload : d
        ),
        error: null,
      };
    
    case 'REMOVE_DOCUMENT':
      return {
        ...state,
        documents: state.documents.filter((d) => d.id !== action.payload),
        error: null,
      };
    
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    
    default:
      return state;
  }
}

interface AppProviderProps {
  children: ReactNode;
}

export function AppProvider({ children }: AppProviderProps) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}
