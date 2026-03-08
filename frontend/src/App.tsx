import './App.css'
import { useState, useCallback, useEffect } from 'react'
import type { ReactNode } from 'react'
import { AppProvider } from './context/AppContext'
import { ThemeProvider } from './context/ThemeContext'
import { useAppContext } from './context/hooks'
import ErrorBoundary from './components/ErrorBoundary'
import { ToastProvider } from './components/Toast'
import ThemeToggle from './components/ThemeToggle'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import ProjectList from './components/ProjectList'
import DocumentManager from './components/DocumentManager'
import ChatList from './components/ChatList'
import ChatInterface from './components/ChatInterface'
import ServerOfflinePage from './components/ServerOfflinePage'
import { useBackendStatus } from './hooks/useBackendStatus'

function AppContent() {
  const { state, dispatch } = useAppContext();
  const selectedProject = state.projects.find(p => p.id === state.selectedProjectId);
  const selectedChat = state.chats.find(c => c.chat_id === state.selectedChatId);
  const [activeTab, setActiveTab] = useState<'documents' | 'chats'>('documents');
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);

  // Global keyboard shortcuts (Ctrl+N for new chat, Escape)
  useKeyboardShortcuts();

  // Auto-switch to chats tab when a chat is newly selected.
  const [prevChatId, setPrevChatId] = useState(state.selectedChatId);
  if (state.selectedChatId !== prevChatId) {
    setPrevChatId(state.selectedChatId);
    if (state.selectedChatId) {
      setActiveTab('chats');
    }
  }

  // Callback for when a project is selected — also closes mobile drawer
  const handleProjectSelected = useCallback(() => {
    setIsMobileDrawerOpen(false);
  }, []);

  // Handle global escape to close mobile drawer
  useEffect(() => {
    const onEscape = () => setIsMobileDrawerOpen(false);
    window.addEventListener('app:escape', onEscape);
    return () => window.removeEventListener('app:escape', onEscape);
  }, []);

  // Handle Ctrl+N: switch to chats tab (ChatList listens for 'app:new-chat' to open modal)
  useEffect(() => {
    const onNewChat = () => {
      if (state.selectedProjectId) {
        setActiveTab('chats');
      }
    };
    window.addEventListener('app:new-chat', onNewChat);
    return () => window.removeEventListener('app:new-chat', onNewChat);
  }, [state.selectedProjectId]);

  const handleSetActiveTab = useCallback((tab: 'documents' | 'chats') => {
    setActiveTab(tab);
  }, []);

  const handleMobileBack = useCallback(() => {
    dispatch({ type: 'SELECT_CHAT', payload: null });
  }, [dispatch]);

  // Calculate desktop widths based on what's shown
  const showChatInterface = activeTab === 'chats' && selectedChat;

  return (
    <div className="flex flex-col h-screen w-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
      {/* ── Mobile Top Bar ── visible only on small screens ── */}
      <header className="md:hidden flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <button
          onClick={() => setIsMobileDrawerOpen(true)}
          className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          aria-label="Open project menu"
        >
          <svg className="w-6 h-6 text-gray-700 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100 truncate">
          {showChatInterface && selectedChat
            ? selectedChat.title
            : selectedProject
              ? selectedProject.title
              : 'Research Assist AI'}
        </h1>
        {showChatInterface ? (
          <button
            onClick={handleMobileBack}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-sm font-medium text-blue-600 dark:text-blue-400"
            aria-label="Back to chat list"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        ) : (
          <div className="w-8" /> /* spacer for centering */
        )}
      </header>

      {/* ── Main content row ── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Backdrop overlay for mobile drawer */}
        {isMobileDrawerOpen && (
          <div
            className="md:hidden fixed inset-0 bg-black/40 z-20 transition-opacity"
            onClick={() => setIsMobileDrawerOpen(false)}
          />
        )}

        {/* ── Left Panel - Project List ── */}
        {/* Mobile: fixed slide-out drawer | Desktop: static sidebar */}
        <aside
          className={`
            fixed inset-y-0 left-0 z-30 w-72 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700
            transform transition-transform duration-200 ease-in-out overflow-y-auto
            ${isMobileDrawerOpen ? 'translate-x-0' : '-translate-x-full'}
            md:relative md:translate-x-0 md:transition-none md:z-auto
            ${showChatInterface ? 'md:w-1/4' : 'md:w-1/3'}
          `}
        >
          {/* Mobile drawer close button */}
          <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <span className="font-semibold text-gray-800 dark:text-gray-200">Projects</span>
            <button
              onClick={() => setIsMobileDrawerOpen(false)}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              aria-label="Close menu"
            >
              <svg className="w-5 h-5 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="p-6">
            {/* Desktop header only */}
            <div className="hidden md:flex md:items-start md:justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Research Assist AI</h1>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">Your research assistant</p>
              </div>
              <ThemeToggle />
            </div>

            <ErrorBoundary>
              <ProjectList onProjectSelected={handleProjectSelected} />
            </ErrorBoundary>
          </div>
        </aside>

        {/* ── Middle Panel - Documents or Chat List ── */}
        {/* On mobile: hidden when chat interface is open */}
        <div
          className={`
            ${showChatInterface ? 'hidden md:flex' : 'flex'}
            flex-col w-full bg-white dark:bg-gray-800 overflow-hidden
            ${showChatInterface ? 'md:w-1/4 md:border-r md:border-gray-200 dark:md:border-gray-700' : 'md:w-2/3'}
            transition-all
          `}
        >
          {selectedProject ? (
            <>
              {/* Tab Navigation */}
              <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shrink-0">
                <nav className="flex px-6 pt-6">
                  <button
                    onClick={() => handleSetActiveTab('documents')}
                    className={`
                      px-4 py-2 font-medium text-sm rounded-t-lg transition-colors
                      ${activeTab === 'documents'
                        ? 'bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                      }
                    `}
                  >
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Documents
                    </div>
                  </button>
                  <button
                    onClick={() => handleSetActiveTab('chats')}
                    className={`
                      px-4 py-2 font-medium text-sm rounded-t-lg transition-colors
                      ${activeTab === 'chats'
                        ? 'bg-white dark:bg-gray-800 text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400'
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                      }
                    `}
                  >
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                      </svg>
                      Chats
                    </div>
                  </button>
                </nav>
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-y-auto">
                <ErrorBoundary>
                  {activeTab === 'documents' ? (
                    <DocumentManager
                      projectId={selectedProject.id}
                      projectTitle={selectedProject.title}
                    />
                  ) : (
                    <ChatList projectId={selectedProject.id} />
                  )}
                </ErrorBoundary>
              </div>
            </>
          ) : (
            /* Empty state when no project selected */
            <div className="flex-1 flex items-center justify-center p-6">
              <div className="max-w-md text-center">
                <svg
                  className="w-24 h-24 mx-auto mb-4 text-gray-300 dark:text-gray-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
                <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200 mb-3">
                  Select a project to start
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Choose a project from the list to upload documents and chat
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ── Right Panel - Chat Interface ── */}
        {/* On mobile: takes full width, replaces middle panel */}
        {showChatInterface && selectedChat && (
          <div className="w-full md:w-1/2 h-full bg-white dark:bg-gray-800 overflow-hidden">
            <ErrorBoundary>
              <ChatInterface
                chatId={selectedChat.chat_id}
                chatTitle={selectedChat.title}
              />
            </ErrorBoundary>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Guards the main application behind a backend availability check.
 * Must live inside ThemeProvider so ServerOfflinePage can use ThemeToggle.
 */
function BackendStatusGate({ children }: { children: ReactNode }) {
  const { isOnline, isChecking, retry } = useBackendStatus();

  if (!isOnline) {
    return <ServerOfflinePage isRetrying={isChecking} onRetry={retry} />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <ThemeProvider>
      <BackendStatusGate>
        <AppProvider>
          <ToastProvider>
            <AppContent />
          </ToastProvider>
        </AppProvider>
      </BackendStatusGate>
    </ThemeProvider>
  )
}

export default App
