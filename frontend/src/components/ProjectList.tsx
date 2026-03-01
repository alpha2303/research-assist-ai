/**
 * ProjectList component - displays list of projects with create/select/delete functionality
 * 
 * Features:
 * - Fetches projects on mount
 * - Create new project button at top
 * - Scrollable list of project cards
 * - Loading skeleton
 * - Error handling
 */

import { useEffect, useState, useCallback } from 'react';
import { useAppContext } from '../context/hooks';
import { projectService } from '../api/projects';
import ProjectCard from './ProjectCard';
import CreateProjectModal from './CreateProjectModal';
import type { ProjectCreate } from '../types';

interface ProjectListProps {
  onProjectSelected?: () => void;
}

export default function ProjectList({ onProjectSelected }: ProjectListProps) {
  const { state, dispatch } = useAppContext();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const loadProjects = useCallback(async () => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const projects = await projectService.getProjects();
      dispatch({ type: 'SET_PROJECTS', payload: projects });
    } catch (error) {
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : 'Failed to load projects',
      });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [dispatch]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreateProject = async (data: ProjectCreate) => {
    const project = await projectService.createProject(data);
    dispatch({ type: 'ADD_PROJECT', payload: project });
    dispatch({ type: 'SELECT_PROJECT', payload: project.id });
    onProjectSelected?.();
  };

  const handleSelectProject = (id: string) => {
    dispatch({ type: 'SELECT_PROJECT', payload: id });
    onProjectSelected?.();
  };

  const handleDeleteProject = async (id: string) => {
    try {
      await projectService.deleteProject(id);
      dispatch({ type: 'DELETE_PROJECT', payload: id });
    } catch (error) {
      dispatch({
        type: 'SET_ERROR',
        payload: error instanceof Error ? error.message : 'Failed to delete project',
      });
    }
  };

  return (
    <div className="space-y-4">
      {/* Create button */}
      <button
        onClick={() => setIsModalOpen(true)}
        className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 font-medium"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        New Project
      </button>

      {/* Project list */}
      <div>
        {state.isLoading && state.projects.length === 0 ? (
          // Loading skeleton
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="p-4 bg-gray-100 dark:bg-gray-700 rounded-lg animate-pulse">
                <div className="h-5 bg-gray-300 dark:bg-gray-600 rounded w-3/4 mb-2"></div>
                <div className="h-4 bg-gray-300 dark:bg-gray-600 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        ) : state.error ? (
          // Error state
          <div className="p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400">
            <p className="font-medium">Error loading projects</p>
            <p className="text-sm mt-1">{state.error}</p>
            <button
              onClick={loadProjects}
              className="mt-2 text-sm text-red-700 hover:text-red-800 underline"
            >
              Try again
            </button>
          </div>
        ) : state.projects.length === 0 ? (
          // Empty state
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            <svg
              className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="text-lg font-medium">No projects yet</p>
            <p className="text-sm mt-1">Create your first project to get started</p>
          </div>
        ) : (
          // Project cards
          <div className="space-y-2">
            {state.projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                isSelected={project.id === state.selectedProjectId}
                onSelect={handleSelectProject}
                onDelete={handleDeleteProject}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create project modal */}
      <CreateProjectModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleCreateProject}
      />
    </div>
  );
}
