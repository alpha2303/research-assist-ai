/**
 * MarkdownContent component — renders AI responses as rich Markdown.
 *
 * Uses `react-markdown` with `remark-gfm` for GitHub-Flavoured Markdown
 * (tables, strikethrough, task lists, autolinks).
 *
 * Custom component overrides style headings, code blocks, links, lists,
 * tables, and block-quotes to match the chat UI design.
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

interface Props {
  /** Raw Markdown text to render */
  content: string;
  /** Additional CSS classes for the wrapper */
  className?: string;
}

/**
 * Shared Tailwind component overrides for react-markdown.
 *
 * We define them once here so every <MarkdownContent /> instance
 * re-uses the same reference (avoids unnecessary re-renders).
 */
const markdownComponents: Components = {
  // ── Headings ────────────────────────────────────────────────
  h1: ({ children, ...props }) => (
    <h1 className="text-xl font-bold mt-4 mb-2" {...props}>{children}</h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="text-lg font-bold mt-3 mb-2" {...props}>{children}</h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="text-base font-semibold mt-3 mb-1" {...props}>{children}</h3>
  ),
  h4: ({ children, ...props }) => (
    <h4 className="text-sm font-semibold mt-2 mb-1" {...props}>{children}</h4>
  ),

  // ── Paragraphs & text ───────────────────────────────────────
  p: ({ children, ...props }) => (
    <p className="mb-2 last:mb-0 leading-relaxed" {...props}>{children}</p>
  ),
  strong: ({ children, ...props }) => (
    <strong className="font-semibold" {...props}>{children}</strong>
  ),
  em: ({ children, ...props }) => (
    <em className="italic" {...props}>{children}</em>
  ),

  // ── Code ────────────────────────────────────────────────────
  code: ({ className, children, ...props }) => {
    // Fenced code blocks get a className like "language-python"
    const isBlock = className?.startsWith('language-');
    if (isBlock) {
      return (
        <code
          className={`block bg-gray-900 text-gray-100 rounded-lg p-3 my-2 text-sm overflow-x-auto whitespace-pre ${className}`}
          {...props}
        >
          {children}
        </code>
      );
    }
    // Inline code
    return (
      <code
        className="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 px-1.5 py-0.5 rounded text-sm font-mono"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children, ...props }) => (
    <pre className="my-2 overflow-x-auto" {...props}>{children}</pre>
  ),

  // ── Lists ───────────────────────────────────────────────────
  ul: ({ children, ...props }) => (
    <ul className="list-disc list-inside mb-2 space-y-1" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="list-decimal list-inside mb-2 space-y-1" {...props}>{children}</ol>
  ),
  li: ({ children, ...props }) => (
    <li className="leading-relaxed" {...props}>{children}</li>
  ),

  // ── Block-quotes ────────────────────────────────────────────
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="border-l-4 border-blue-300 dark:border-blue-600 bg-blue-50 dark:bg-blue-900/20 pl-4 py-2 my-2 text-gray-700 dark:text-gray-300 italic"
      {...props}
    >
      {children}
    </blockquote>
  ),

  // ── Tables ──────────────────────────────────────────────────
  table: ({ children, ...props }) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full border-collapse text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead className="bg-gray-100 dark:bg-gray-700" {...props}>{children}</thead>
  ),
  th: ({ children, ...props }) => (
    <th className="border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-left font-semibold" {...props}>
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="border border-gray-300 dark:border-gray-600 px-3 py-1.5" {...props}>{children}</td>
  ),

  // ── Links ───────────────────────────────────────────────────
  a: ({ children, href, ...props }) => (
    <a
      href={href}
      className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 underline"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  ),

  // ── Horizontal rule ─────────────────────────────────────────
  hr: (props) => <hr className="my-3 border-gray-300 dark:border-gray-600" {...props} />,
};

export default function MarkdownContent({ content, className = '' }: Props) {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
