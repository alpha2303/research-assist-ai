/**
 * ChatInterface component - full chat conversation interface with SSE streaming
 *
 * Features (Phase 5.8):
 * - Message history display
 * - Message input with send button
 * - Real-time token streaming via SSE
 * - Source references with document attribution
 * - Auto-scroll to latest messages
 * - Loading and error states
 */

import { useEffect, useRef, useState } from 'react';
import { getMessages, sendMessageStream } from '../api/chats';
import MarkdownContent from './MarkdownContent';
import type { Message, SourceReference } from '../types';

interface Props {
  chatId: string;
  chatTitle: string;
}

interface StreamingMessage {
  role: 'assistant';
  content: string;
  isStreaming: boolean;
  sources?: Array<{ document_id: string; document_title: string; page_number: number | null; chunk_id: string }>;
}

export default function ChatInterface({ chatId, chatTitle }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingMessage, setStreamingMessage] = useState<StreamingMessage | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const streamingRef = useRef<StreamingMessage | null>(null);

  // Load message history when chat changes
  useEffect(() => {
    let cancelled = false;

    const loadMessages = async () => {
      setIsLoading(true);
      setError(null);
      setStreamingMessage(null);
      try {
        const response = await getMessages(chatId);
        if (!cancelled) setMessages(response.items);
      } catch (err) {
        if (!cancelled) setError('Failed to load messages.');
        console.error('Failed to load messages:', err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    loadMessages();
    return () => { cancelled = true; };
  }, [chatId]);

  // Auto-scroll on new content
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage?.content]);

  // Cleanup abort controller on unmount or chat change
  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); };
  }, [chatId]);

  const handleSend = () => {
    const content = input.trim();
    if (!content || isSending) return;

    setInput('');
    setIsSending(true);
    setError(null);

    // Optimistically add user message
    const optimisticUserMsg: Message = {
      message_id: `tmp-${Date.now()}`,
      chat_id: chatId,
      sender: 'user',
      content,
      sources: null,
      token_count: null,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUserMsg]);

    // Start streaming assistant response
    setStreamingMessage({ role: 'assistant', content: '', isStreaming: true });
    streamingRef.current = { role: 'assistant', content: '', isStreaming: true };

    abortControllerRef.current = sendMessageStream(chatId, content, (event) => {
      if (event.type === 'token') {
        setStreamingMessage((prev) => {
          const next = prev ? { ...prev, content: prev.content + event.content } : null;
          streamingRef.current = next;
          return next;
        });
      } else if (event.type === 'sources') {
        setStreamingMessage((prev) => {
          const next = prev ? { ...prev, sources: event.sources } : null;
          streamingRef.current = next;
          return next;
        });
      } else if (event.type === 'done') {
        // Read final streaming content from ref (avoids side effects inside state updater)
        const prev = streamingRef.current;
        streamingRef.current = null;
        setStreamingMessage(null);

        if (prev) {
          const finalMsg: Message = {
            message_id: event.message_id,
            chat_id: chatId,
            sender: 'assistant',
            content: prev.content,
            sources: prev.sources
              ? prev.sources.map((s) => ({
                  document_id: s.document_id,
                  document_title: s.document_title,
                  chunk_id: s.chunk_id,
                  chunk_index: 0,
                  page_number: s.page_number,
                  section_heading: null,
                  similarity_score: 0,
                  content_preview: '',
                }))
              : null,
            token_count: null,
            timestamp: new Date().toISOString(),
          };
          setMessages((m) => [...m, finalMsg]);
        }
        setIsSending(false);
      } else if (event.type === 'error') {
        streamingRef.current = null;
        setStreamingMessage(null);
        setError(`Error: ${event.error}`);
        setIsSending(false);
      }
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCancel = () => {
    abortControllerRef.current?.abort();
    streamingRef.current = null;
    setStreamingMessage(null);
    setIsSending(false);
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading messages…</p>
        </div>
      </div>
    );
  }

  const allDisplayedMessages = messages;

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Chat Header */}
      <div className="border-b border-gray-200 dark:border-gray-700 px-6 py-4 bg-white dark:bg-gray-800">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{chatTitle}</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {messages.length} {messages.length === 1 ? 'message' : 'messages'}
        </p>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 bg-gray-50 dark:bg-gray-900">
        {allDisplayedMessages.length === 0 && !streamingMessage ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <svg className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">Start the conversation</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">Ask a question about your documents</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-w-4xl mx-auto">
            {allDisplayedMessages.map((message) => (
              <MessageBubble key={message.message_id} message={message} />
            ))}

            {/* Streaming message */}
            {streamingMessage && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-lg px-4 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100">
                  {streamingMessage.content ? (
                    <MarkdownContent content={streamingMessage.content} />
                  ) : (
                    <div className="flex items-center gap-1">
                      <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  )}
                  {streamingMessage.isStreaming && (
                    <span className="inline-block w-0.5 h-4 bg-gray-600 dark:bg-gray-400 animate-pulse ml-0.5 align-text-bottom" />
                  )}
                </div>
              </div>
            )}

            {error && (
              <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg px-4 py-3 text-red-700 dark:text-red-300 text-sm">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-white dark:bg-gray-800">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-2 items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your documents… (Enter to send, Shift+Enter for newline)"
              disabled={isSending}
              rows={1}
              className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 dark:disabled:bg-gray-700 disabled:text-gray-500 dark:disabled:text-gray-400 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500"
              style={{ maxHeight: '150px', overflowY: 'auto' }}
              onInput={(e) => {
                const target = e.currentTarget;
                target.style.height = 'auto';
                target.style.height = `${Math.min(target.scrollHeight, 150)}px`;
              }}
            />
            {isSending ? (
              <button
                onClick={handleCancel}
                className="px-4 py-3 bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-600 dark:text-red-400 rounded-lg transition-colors"
                title="Cancel"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white rounded-lg transition-colors"
                title="Send"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.sender === 'user';
  const [showSources, setShowSources] = useState(false);
  const hasSources = message.sources && message.sources.length > 0;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <MarkdownContent content={message.content} />
        )}

        <div className={`flex items-center justify-between mt-2 ${isUser ? 'text-blue-100' : 'text-gray-400 dark:text-gray-500'}`}>
          <span className="text-xs">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
          {hasSources && (
            <button
              onClick={() => setShowSources((s) => !s)}
              className={`text-xs underline ml-4 ${isUser ? 'text-blue-100 hover:text-white' : 'text-blue-500 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300'}`}
            >
              {showSources ? 'Hide sources' : `${message.sources!.length} source${message.sources!.length !== 1 ? 's' : ''}`}
            </button>
          )}
        </div>

        {hasSources && showSources && (
          <SourceList sources={message.sources!} />
        )}
      </div>
    </div>
  );
}

function SourceList({ sources }: { sources: SourceReference[] }) {
  return (
    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 space-y-2">
      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Sources</p>
      {sources.map((s, i) => (
        <div key={i} className="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50 rounded px-2 py-1">
          <span className="font-medium text-gray-800 dark:text-gray-200">{s.document_title}</span>
          {s.page_number != null && (
            <span className="ml-1 text-gray-400 dark:text-gray-500">— p. {s.page_number}</span>
          )}
        </div>
      ))}
    </div>
  );
}
