/**
 * ServerOfflinePage — shown when the backend cannot be reached.
 *
 * Design mirrors the main application: same colour palette, typography,
 * dark-mode support, and component styles (card, button).
 */

import ThemeToggle from './ThemeToggle';

interface Props {
  /** True while a reconnection attempt is in flight. */
  isRetrying: boolean;
  /** Called when the user clicks "Try Reconnecting". */
  onRetry: () => void;
}

export default function ServerOfflinePage({ isRetrying, onRetry }: Props) {
  return (
    <div className="flex flex-col h-screen w-screen bg-gray-50 dark:bg-gray-900">
      {/* ── Minimal top bar ── */}
      <header className="flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <div className="flex items-center gap-2">
          {/* App logo mark */}
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
            <svg
              className="w-4 h-4 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
          <span className="font-semibold text-gray-900 dark:text-gray-100 text-sm">
            Research Assist AI
          </span>
        </div>
        <ThemeToggle />
      </header>

      {/* ── Centred content ── */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-200 dark:border-gray-700 p-10 text-center">

          {/* Icon — server rack with a diagonal slash */}
          <div className="flex items-center justify-center w-20 h-20 mx-auto mb-6 rounded-full bg-gray-100 dark:bg-gray-700">
            <svg
              className="w-10 h-10 text-gray-400 dark:text-gray-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {/* Server rack — two stacked server units */}
              <rect x="3" y="4"  width="18" height="5" rx="1" />
              <rect x="3" y="13" width="18" height="5" rx="1" />
              {/* Status indicator lights */}
              <circle cx="6.5" cy="6.5"  r="0.75" fill="currentColor" stroke="none" />
              <circle cx="6.5" cy="15.5" r="0.75" fill="currentColor" stroke="none" />
              {/* Diagonal "offline" slash */}
              <line x1="2" y1="2" x2="22" y2="22" />
            </svg>
          </div>

          {/* Witty heading — research-themed */}
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-3">
            Peer review has nothing on this wait.
          </h1>

          {/* Exact required message */}
          <p className="text-base font-semibold text-gray-700 dark:text-gray-300 mb-3">
            Server is currently offline.
          </p>

          {/* Flavour text */}
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-8 leading-relaxed">
            Our server has stepped away from the lab for a bit.
            We'll keep checking — it should be back well before your next
            deadline.
          </p>

          {/* Retry button */}
          <button
            onClick={onRetry}
            disabled={isRetrying}
            className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
          >
            {isRetrying ? (
              <span className="flex items-center gap-2 justify-center">
                <svg
                  className="w-4 h-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                Checking…
              </span>
            ) : (
              'Try Reconnecting'
            )}
          </button>

          {/* Auto-retry note */}
          <p className="mt-4 text-xs text-gray-400 dark:text-gray-500">
            Automatically retrying every 30 seconds (up to 3 times).
          </p>
        </div>
      </main>
    </div>
  );
}
