/**
 * DocumentManager component - manages documents for a project
 * 
 * Features:
 * - Upload area for new documents
 * - List of documents with status
 * - Auto-refresh status polling
 */

import { useState, useEffect, useCallback } from 'react';
import { documentService } from '../api/documents';
import DocumentUploadArea from './DocumentUploadArea';
import DocumentListItem from './DocumentListItem';
import type { Document } from '../types';

interface Props {
  projectId: string;
  projectTitle: string;
}

export default function DocumentManager({ projectId, projectTitle }: Props) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await documentService.getProjectDocuments(projectId);
      setDocuments(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleUploadComplete = () => {
    // Reload document list after upload
    loadDocuments();
  };

  const handleDelete = async (documentId: string) => {
    await documentService.unlinkFromProject(projectId, documentId);
    // Remove from local state
    setDocuments((prev) => prev.filter((doc) => doc.id !== documentId));
  };

  const handleStatusUpdate = useCallback(async (documentId: string) => {
    try {
      const status = await documentService.getDocumentStatus(documentId);
      
      // Update document in local state
      setDocuments((prev) =>
        prev.map((doc) =>
          doc.id === documentId
            ? {
                ...doc,
                status: status.status as Document['status'],
                page_count: status.page_count,
              }
            : doc
        )
      );
    } catch (err) {
      console.error('Failed to update document status:', err);
    }
  }, []);

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
          <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
          <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">{projectTitle}</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {documents.length} {documents.length === 1 ? 'document' : 'documents'}
        </p>
      </div>

      {/* Upload Area */}
      <DocumentUploadArea projectId={projectId} onUploadComplete={handleUploadComplete} />

      {/* Error */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-sm text-red-800 dark:text-red-300">{error}</p>
          <button
            onClick={loadDocuments}
            className="mt-2 text-sm font-medium text-red-600 hover:text-red-700"
          >
            Try again
          </button>
        </div>
      )}

      {/* Document List */}
      {documents.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Documents</h3>
          {documents.map((document) => (
            <DocumentListItem
              key={document.id}
              document={document}
              onDelete={handleDelete}
              onStatusUpdate={handleStatusUpdate}
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
              d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
          <p className="text-gray-500 dark:text-gray-400">No documents yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">Upload PDFs to get started</p>
        </div>
      ) : null}
    </div>
  );
}
