/**
 * API service for document operations
 */

import apiClient from './client';
import type { Document, DocumentUploadResponse, DocumentStatusResponse } from '../types';

export const documentService = {
  /**
   * Upload a document file
   */
  async uploadDocument(file: File): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post<DocumentUploadResponse>(
      '/api/documents/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );

    return response.data;
  },

  /**
   * Link a document to a project
   */
  async linkToProject(projectId: string, documentId: string): Promise<void> {
    await apiClient.post(`/api/projects/${projectId}/documents`, {
      document_id: documentId,
    });
  },

  /**
   * Get all documents for a project
   */
  async getProjectDocuments(
    projectId: string,
    limit: number = 50,
    offset: number = 0
  ): Promise<{ items: Document[]; total: number }> {
    const response = await apiClient.get<{ items: Document[]; total: number }>(
      `/api/projects/${projectId}/documents`,
      {
        params: { limit, offset },
      }
    );

    return response.data;
  },

  /**
   * Get document processing status
   */
  async getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
    const response = await apiClient.get<DocumentStatusResponse>(
      `/api/documents/${documentId}/status`
    );

    return response.data;
  },

  /**
   * Unlink a document from a project
   */
  async unlinkFromProject(projectId: string, documentId: string): Promise<void> {
    await apiClient.delete(`/api/projects/${projectId}/documents/${documentId}`);
  },
};
