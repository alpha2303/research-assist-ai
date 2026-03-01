/**
 * Types for the application state and API responses
 */

export interface Project {
  id: string;
  title: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  document_count: number;
}

export interface ProjectCreate {
  title: string;
  description?: string | null;
}

export interface ProjectUpdate {
  title?: string;
  description?: string | null;
}

export interface Document {
  id: string;
  title: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  page_count: number | null;
  file_size_bytes: number;
  created_at: string;
}

export interface DocumentUploadResponse {
  id: string;
  title: string;
  file_hash: string;
  file_size_bytes: number;
  mime_type: string;
  status: string;
  s3_key: string;
  created_at: string;
  is_duplicate: boolean;
}

export interface DocumentStatusResponse {
  id: string;
  title: string;
  status: string;
  error_message: string | null;
  page_count: number | null;
  file_size_bytes: number;
  mime_type: string;
  created_at: string;
}

export interface Chat {
  chat_id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatCreate {
  title?: string | null;
}

export interface SourceReference {
  document_id: string;
  document_title: string;
  chunk_id: string | null;
  chunk_index: number | null;
  page_number: number | null;
  section_heading: string | null;
  similarity_score: number | null;
  content_preview: string | null;
}

export interface Message {
  message_id: string;
  chat_id: string;
  sender: 'user' | 'assistant';
  content: string;
  sources: SourceReference[] | null;
  token_count: number | null;
  timestamp: string;
}

export interface MessageCreate {
  content: string;
}

export interface AppState {
  projects: Project[];
  selectedProjectId: string | null;
  selectedChatId: string | null;
  chats: Chat[];
  messages: Message[];
  documents: Document[];
  isLoading: boolean;
  error: string | null;
}

export type AppAction =
  | { type: 'SET_PROJECTS'; payload: Project[] }
  | { type: 'ADD_PROJECT'; payload: Project }
  | { type: 'UPDATE_PROJECT'; payload: Project }
  | { type: 'DELETE_PROJECT'; payload: string }
  | { type: 'SELECT_PROJECT'; payload: string | null }
  | { type: 'SELECT_CHAT'; payload: string | null }
  | { type: 'SET_CHATS'; payload: Chat[] }
  | { type: 'ADD_CHAT'; payload: Chat }
  | { type: 'UPDATE_CHAT'; payload: Chat }
  | { type: 'DELETE_CHAT'; payload: string }
  | { type: 'SET_MESSAGES'; payload: Message[] }
  | { type: 'ADD_MESSAGE'; payload: Message }
  | { type: 'SET_DOCUMENTS'; payload: Document[] }
  | { type: 'ADD_DOCUMENT'; payload: Document }
  | { type: 'UPDATE_DOCUMENT'; payload: Document }
  | { type: 'REMOVE_DOCUMENT'; payload: string }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };
