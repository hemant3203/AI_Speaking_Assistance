/** Page title block. Also sets the document title, so tabs and screen readers name the page. */
import { useEffect } from 'react';

export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · Spotlight` : 'Spotlight';
  }, [title]);
}

export function PageHeader({ title, description, actions }) {
  useDocumentTitle(title);
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4 lg:mb-8">
      <div className="min-w-0">
        <h1 className="text-3xl font-bold sm:text-4xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-ink-soft">{description}</p>}
      </div>
      {actions}
    </header>
  );
}
