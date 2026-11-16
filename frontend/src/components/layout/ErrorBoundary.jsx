/** Last line of defence: reports render crashes and offers a way back instead of a blank page. */
import { Component } from 'react';
import { logger } from '../../lib/logger';

export class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    logger.error(error?.message || 'Render error', { name: error?.name, stack: info?.componentStack?.slice(0, 400) });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="flex min-h-dvh items-center justify-center px-6 text-center">
        <div className="max-w-md">
          <h1 className="text-3xl font-bold">The lights flickered</h1>
          <p className="mt-3 text-ink-soft">
            Something broke on this page. Your sessions and streak are safe. Reloading usually puts things right.
          </p>
          <button
            type="button"
            onClick={() => window.location.assign('/')}
            className="mt-6 min-h-11 rounded-xl bg-amber px-5 font-semibold text-on-amber hover:bg-amber-bright"
          >
            Reload Spotlight
          </button>
        </div>
      </main>
    );
  }
}
