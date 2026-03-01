/**
 * ChatListItem component - displays a single chat in the chat list
 * 
 * Features:
 * - Shows chat title and metadata (message count, last updated)
 * - Click to select chat
 * - Delete button
 * - Visual indication when selected
 */

import type { Chat } from '../types';

interface ChatListItemProps {
  chat: Chat;
  isSelected: boolean;
  onSelect: (chatId: string) => void;
  onDelete: (chatId: string) => void;
}

export default function ChatListItem({
  chat,
  isSelected,
  onSelect,
  onDelete,
}: ChatListItemProps) {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (window.confirm(`Delete chat "${chat.title}"?`)) {
      onDelete(chat.chat_id);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString();
  };

  return (
    <div
      onClick={() => onSelect(chat.chat_id)}
      className={`
        p-3 rounded-lg shadow-sm cursor-pointer transition-all
        ${isSelected 
          ? 'bg-blue-50 dark:bg-blue-900/30 border-2 border-blue-500 shadow-md' 
          : 'bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-750 hover:shadow-md'
        }
      `}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-gray-900 dark:text-gray-100 truncate">
            {chat.title}
          </h4>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 dark:text-gray-400">
            <span className="flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              {chat.message_count}
            </span>
            <span>
              {formatDate(chat.updated_at)}
            </span>
          </div>
        </div>
        
        <button
          onClick={handleDelete}
          className="p-1 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
          title="Delete chat"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>
  );
}
