/**
 * ChatList component - manages chats for a project
 * 
 * Features:
 * - Create new chat button
 * - List of chats with metadata
 * - Click to select and view chat
 * - Delete chats
 */

import { useState, useEffect, useCallback } from 'react';
import { listChats, createChat, deleteChat } from '../api/chats';
import { useAppContext } from '../context/hooks';
import CreateChatModal from './CreateChatModal';
import ChatListItem from './ChatListItem';
import type { ChatCreate } from '../types';

interface Props {
  projectId: string;
}

export default function ChatList({ projectId }: Props) {
  const { state, dispatch } = useAppContext();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const loadChats = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await listChats(projectId);
      dispatch({ type: 'SET_CHATS', payload: response.items });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chats');
    } finally {
      setIsLoading(false);
    }
  }, [projectId, dispatch]);

  useEffect(() => {
    loadChats();
  }, [loadChats]);

  // Listen for global Ctrl+N shortcut to open create modal
  useEffect(() => {
    const onNewChat = () => setIsCreateModalOpen(true);
    window.addEventListener('app:new-chat', onNewChat);
    return () => window.removeEventListener('app:new-chat', onNewChat);
  }, []);

  const handleCreateChat = async (data: ChatCreate) => {
    const newChat = await createChat(projectId, data);
    dispatch({ type: 'ADD_CHAT', payload: newChat });
    dispatch({ type: 'SELECT_CHAT', payload: newChat.chat_id });
  };

  const handleSelectChat = (chatId: string) => {
    dispatch({ type: 'SELECT_CHAT', payload: chatId });
  };

  const handleDeleteChat = async (chatId: string) => {
    try {
      await deleteChat(chatId);
      dispatch({ type: 'DELETE_CHAT', payload: chatId });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete chat');
    }
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
          <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
        </div>
      </div>
    );
  }

  // Filter chats for the current project
  const projectChats = state.chats.filter(chat => chat.project_id === projectId);

  return (
    <div className="p-6 space-y-4">
      {/* Header with Create Button */}
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 truncate">Chats</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {projectChats.length} {projectChats.length === 1 ? 'chat' : 'chats'}
          </p>
        </div>
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="flex items-center gap-2 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shrink-0 whitespace-nowrap text-sm"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          New Chat
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-sm text-red-800 dark:text-red-300">{error}</p>
          <button
            onClick={loadChats}
            className="mt-2 text-sm font-medium text-red-600 hover:text-red-700"
          >
            Try again
          </button>
        </div>
      )}

      {/* Chat List */}
      {projectChats.length > 0 ? (
        <div className="space-y-2">
          {projectChats.map((chat) => (
            <ChatListItem
              key={chat.chat_id}
              chat={chat}
              isSelected={state.selectedChatId === chat.chat_id}
              onSelect={handleSelectChat}
              onDelete={handleDeleteChat}
            />
          ))}
        </div>
      ) : !isLoading && !error ? (
        <div className="text-center py-12">
          <svg
            className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
            />
          </svg>
          <p className="text-gray-500 dark:text-gray-400 mb-2">No chats yet</p>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            Start your first chat
          </button>
        </div>
      ) : null}

      {/* Create Chat Modal */}
      <CreateChatModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleCreateChat}
      />
    </div>
  );
}
