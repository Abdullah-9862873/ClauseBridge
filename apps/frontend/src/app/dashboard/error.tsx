'use client';

import { useEffect } from 'react';

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Dashboard error:', error);
  }, [error]);

  return (
    <div style={{
      padding: '60px 20px',
      textAlign: 'center',
    }}>
      <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--ink)', marginBottom: '8px' }}>
        Failed to load dashboard
      </h2>
      <p style={{ fontSize: '14px', color: 'var(--ink-50)', marginBottom: '20px' }}>
        {error.message || 'An unexpected error occurred'}
      </p>
      <button onClick={reset} className="btn btn-ghost btn-sm">
        Try again
      </button>
    </div>
  );
}
