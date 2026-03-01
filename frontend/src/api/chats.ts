import apiClient from './client';
import type { Chat, ChatCreate, Message } from '../types';

export interface ChatListResponse {
  items: Chat[];
  total: number;
  limit: number;
  offset: number;
}

export interface MessageListResponse {
  items: Message[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Create a new chat session for a project
 */
export const createChat = async (projectId: string, data: ChatCreate): Promise<Chat> => {
  const response = await apiClient.post<Chat>(`/api/projects/${projectId}/chats`, data);
  return response.data;
};

/**
 * List all chats for a project
 */
export const listChats = async (
  projectId: string,
  limit: number = 20
): Promise<ChatListResponse> => {
  const params: Record<string, string | number> = { limit };
  const response = await apiClient.get<ChatListResponse>(`/api/projects/${projectId}/chats`, { params });
  return response.data;
};

/**
 * Get a specific chat by ID
 */
export const getChat = async (chatId: string): Promise<Chat> => {
  const response = await apiClient.get<Chat>(`/api/chats/${chatId}`);
  return response.data;
};

/**
 * Delete a chat session
 */
export const deleteChat = async (chatId: string): Promise<void> => {
  await apiClient.delete(`/api/chats/${chatId}`);
};

/**
 * Get messages for a chat session
 */
export const getMessages = async (
  chatId: string,
  limit: number = 50
): Promise<MessageListResponse> => {
  const params: Record<string, string | number> = { limit };
  const response = await apiClient.get<MessageListResponse>(`/api/chats/${chatId}/messages`, { params });
  return response.data;
};

/**
 * Send a message to a chat (placeholder for Phase 5.6 SSE)
 * This will be replaced with Server-Sent Events implementation
 */
export const sendMessage = async (chatId: string, content: string): Promise<Message> => {
  const response = await apiClient.post<Message>(`/api/chats/${chatId}/messages`, { content });
  return response.data;
};

export type SSEEvent =
  | { type: 'token'; content: string }
  | { type: 'sources'; sources: Array<{ document_id: string; document_title: string; page_number: number | null; chunk_id: string }> }
  | { type: 'done'; message_id: string }
  | { type: 'error'; error: string };

/**
 * Send a message to a chat and receive a real-time streaming response via SSE.
 *
 * Includes automatic reconnection with exponential backoff (max 3 attempts).
 *
 * @param chatId - The chat session ID
 * @param content - The user message content
 * @param onEvent - Callback for each SSE event
 * @returns AbortController to cancel the stream
 */
export const sendMessageStream = (
  chatId: string,
  content: string,
  onEvent: (event: SSEEvent) => void
): AbortController => {
  const controller = new AbortController();
  const MAX_SSE_RETRIES = 3;
  const BASE_DELAY_MS = 1000;

  (async () => {
    const API_BASE = (apiClient.defaults.baseURL ?? '') as string;
    let attempt = 0;

    while (attempt <= MAX_SSE_RETRIES) {
      try {
        const response = await fetch(`${API_BASE}/api/chats/${chatId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content }),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          // 4xx errors are non-retryable
          if (response.status >= 400 && response.status < 500) {
            onEvent({ type: 'error', error: `HTTP ${response.status}` });
            return;
          }
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE events from buffer
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';  // Keep incomplete last line

          let currentEventType = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                onEvent({ type: currentEventType as SSEEvent['type'], ...data });
              } catch {
                // Ignore parse errors
              }
              currentEventType = '';
            }
          }
        }

        // Stream completed successfully — exit retry loop
        return;
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          return; // User cancelled — don't retry
        }

        attempt++;
        if (attempt > MAX_SSE_RETRIES) {
          onEvent({ type: 'error', error: String(err) });
          return;
        }

        // Exponential backoff before retrying
        const delay = BASE_DELAY_MS * Math.pow(2, attempt - 1);
        console.warn(`SSE attempt ${attempt} failed, retrying in ${delay}ms…`, err);
        await new Promise((r) => setTimeout(r, delay));
      }
    }
  })();

  return controller;
};
