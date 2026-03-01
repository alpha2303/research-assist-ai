/**
 * ProjectCard component - displays a single project in the list
 * 
 * Features:
 * - Click to select/highlight
 * - Shows title and document count
 * - Delete button with confirmation
 */

import type { Project } from '../types';

interface ProjectCardProps {
  project: Project;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function ProjectCard({
  project,
  isSelected,
  onSelect,
  onDelete,
}: ProjectCardProps) {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent selecting when deleting
    
    if (confirm(`Delete "${project.title}"? This action cannot be undone.`)) {
      onDelete(project.id);
    }
  };

  return (
    <div
      onClick={() => onSelect(project.id)}
      className={`
        p-4 mb-2 rounded-lg shadow-sm cursor-pointer transition-all
        ${isSelected
          ? 'bg-blue-50 dark:bg-blue-900/30 border-2 border-blue-500 shadow-md'
          : 'bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'
        }
      `}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 truncate">
            {project.title}
          </h3>
          {project.description && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
              {project.description}
            </p>
          )}
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
            {project.document_count} {project.document_count === 1 ? 'document' : 'documents'}
          </p>
        </div>
        
        <button
          onClick={handleDelete}
          className="ml-2 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
          title="Delete project"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
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
