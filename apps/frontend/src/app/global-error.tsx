'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Application error:', error);
  }, [error]);

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--paper)',
      fontFamily: 'inherit',
    }}>
      <div style={{
        maxWidth: '400px',
        textAlign: 'center',
        padding: '40px',
      }}>
        <div style={{
          fontSize: '48px',
          marginBottom: '16px',
        }}>
          !
        </div>
        <h2 style={{
          fontSize: '18px',
          fontWeight: 600,
          color: 'var(--ink)',
          marginBottom: '8px',
        }}>
          Something went wrong
        </h2>
        <p style={{
          fontSize: '14px',
          color: 'var(--ink-50)',
          marginBottom: '24px',
          lineHeight: 1.5,
        }}>
          An unexpected error occurred. Please try again.
        </p>
        <button
          onClick={reset}
          className="btn btn-primary"
          style={{ width: 'auto' }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}
