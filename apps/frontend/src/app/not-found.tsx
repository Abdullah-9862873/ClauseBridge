export default function NotFound() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--paper)',
    }}>
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <div style={{
          fontSize: '64px',
          fontWeight: 700,
          color: 'var(--ink)',
          lineHeight: 1,
          marginBottom: '16px',
        }}>
          404
        </div>
        <h2 style={{
          fontSize: '18px',
          fontWeight: 600,
          color: 'var(--ink)',
          marginBottom: '8px',
        }}>
          Page not found
        </h2>
        <p style={{
          fontSize: '14px',
          color: 'var(--ink-50)',
          marginBottom: '24px',
        }}>
          The page you are looking for does not exist.
        </p>
        <a href="/dashboard" className="btn btn-primary" style={{ width: 'auto' }}>
          Go to Dashboard
        </a>
      </div>
    </div>
  );
}
