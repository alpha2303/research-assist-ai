/**
 * API service for project operations
 * 
 * All project-related API calls are centralized here.
 */

import api from './client';
import type { Project, ProjectCreate, ProjectUpdate } from '../types';

interface ProjectListResponse {
  items: Project[];
  total: number;
  limit: number;
  offset: number;
}

export const projectService = {
  /**
   * Fetch all projects
   */
  async getProjects(): Promise<Project[]> {
    const response = await api.get<ProjectListResponse>('/api/projects');
    return response.data.items;
  },

  /**
   * Fetch a single project by ID
   */
  async getProject(id: string): Promise<Project> {
    const response = await api.get<Project>(`/api/projects/${id}`);
    return response.data;
  },

  /**
   * Create a new project
   */
  async createProject(data: ProjectCreate): Promise<Project> {
    const response = await api.post<Project>('/api/projects', data);
    return response.data;
  },

  /**
   * Update an existing project
   */
  async updateProject(id: string, data: ProjectUpdate): Promise<Project> {
    const response = await api.put<Project>(`/api/projects/${id}`, data);
    return response.data;
  },

  /**
   * Delete a project
   */
  async deleteProject(id: string): Promise<void> {
    await api.delete(`/api/projects/${id}`);
  },
};
