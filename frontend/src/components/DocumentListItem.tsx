/**
 * DocumentListItem component - individual document card with status
 * 
 * Features:
 * - Status badge (queued/processing/ready/failed)
 * - File size and page count display
 * - Delete button
 * - Auto-refresh while processing
 */

import { useState, useEffect } from 'react';
import type { Document } from '../types';

interface Props {
  document: Document;
  onDelete: (documentId: string) => void;
  onStatusUpdate: (documentId: string) => void;
}

export default function DocumentListItem({
  document,
  onDelete,
  onStatusUpdate,
}: Props) {
  const [isDeleting, setIsDeleting] = useState(false);

  // Auto-refresh status while processing
  useEffect(() => {
    if (document.status === 'queued' || document.status === 'processing') {
      const interval = setInterval(() => {
        onStatusUpdate(document.id);
      }, 3000); // Poll every 3 seconds

      return () => clearInterval(interval);
    }
  }, [document.id, document.status, onStatusUpdate]);

  const handleDelete = async () => {
    if (!confirm(`Delete ${document.title}?`)) return;

    setIsDeleting(true);
    try {
      await onDelete(document.id);
    } catch {
      setIsDeleting(false);
      alert('Failed to delete document');
    }
  };

  const getStatusBadge = () => {
    switch (document.status) {
      case 'queued':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300">
            <span className="h-2 w-2 rounded-full bg-yellow-400 mr-1"></span>
            Queued
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300">
            <span className="h-2 w-2 rounded-full bg-blue-400 mr-1 animate-pulse"></span>
            Processing
          </span>
        );
      case 'completed':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
            <span className="h-2 w-2 rounded-full bg-green-400 mr-1"></span>
            Ready
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300">
            <span className="h-2 w-2 rounded-full bg-red-400 mr-1"></span>
            Failed
          </span>
        );
      default:
        return null;
    }
  };

  const formatFileSize = (bytes: number): string => {
    const mb = bytes / (1024 * 1024);
    return mb < 1 ? `${(bytes / 1024).toFixed(1)} KB` : `${mb.toFixed(1)} MB`;
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border-2 border-gray-200 dark:border-gray-700 shadow-sm p-4 hover:shadow-md transition-all">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            {/* PDF Icon */}
            <svg
              className="h-5 w-5 text-red-500 flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
                clipRule="evenodd"
              />
            </svg>
            
            {/* Title */}
            <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
              {document.title}
            </h3>
          </div>

          {/* Status Badge */}
          <div className="mb-2">{getStatusBadge()}</div>

          {/* Metadata */}
          <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
            <span>{formatFileSize(document.file_size_bytes)}</span>
            {document.page_count && (
              <>
                <span>•</span>
                <span>{document.page_count} pages</span>
              </>
            )}
          </div>
        </div>

        {/* Delete Button */}
        <button
          onClick={handleDelete}
          disabled={isDeleting}
          className="ml-2 p-1 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors disabled:opacity-50"
          title="Delete document"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
