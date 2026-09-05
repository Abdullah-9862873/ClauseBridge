'use client';

import { useState } from 'react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firmName, setFirmName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'login' | 'signup'>('login');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        throw new Error('Invalid email or password');
      }

      const data = await res.json();
      localStorage.setItem('access_token', data.access_token);
      window.location.href = '/dashboard';
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/v1/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ firm_name: firmName, email, password }),
      });

      if (!res.ok) {
        throw new Error('Email already registered');
      }

      const loginRes = await fetch('http://localhost:8000/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (loginRes.ok) {
        const data = await loginRes.json();
        localStorage.setItem('access_token', data.access_token);
        window.location.href = '/dashboard';
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-brand">
        <div>
          <div className="mark">
            <svg width="24" height="24" viewBox="0 0 26 26" fill="none">
              <path d="M4 21V6.5C4 5.12 5.12 4 6.5 4H15L22 11V19.5C22 20.88 20.88 22 19.5 22H6.5C5.12 22 4 20.88 4 19.5Z" stroke="#F7F6F1" strokeWidth="1.4"/>
              <path d="M15 4V9.5C15 10.33 15.67 11 16.5 11H22" stroke="#F7F6F1" strokeWidth="1.4"/>
              <line x1="8" y1="14.5" x2="17.5" y2="14.5" stroke="#B23B2E" strokeWidth="1.4"/>
              <line x1="8" y1="17.6" x2="14" y2="17.6" stroke="#F7F6F1" strokeWidth="1.4"/>
            </svg>
            Clausebridge
          </div>
        </div>
        <blockquote>
          &ldquo;It didn&rsquo;t catch a typo. It caught that our counterparty had quietly widened a liability cap &mdash; three clauses away from where anyone was looking.&rdquo;
          <div className="attr">Meredith Okonkwo &mdash; Partner, Voss &amp; Okonkwo LLP</div>
        </blockquote>
        <div style={{ fontSize: '12.5px', color: 'var(--sidebar-text)' }}>&copy; 2026 Clausebridge</div>
      </div>

      <div className="login-form-side">
        <div className="login-card">
          <h1>{mode === 'login' ? 'Sign in' : 'Create firm'}</h1>
          <p className="lede">Review today&apos;s drafts, or pick up where your team left off.</p>

          {mode === 'signup' && (
            <div className="field">
              <label htmlFor="firmName">Firm name</label>
              <input
                id="firmName"
                type="text"
                value={firmName}
                onChange={(e) => setFirmName(e.target.value)}
                placeholder="e.g. Smith & Associates"
                required
              />
            </div>
          )}

          <form onSubmit={mode === 'login' ? handleLogin : handleSignup}>
            <div className="field">
              <label htmlFor="email">Work email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@lawfirm.com"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;"
                required
              />
            </div>

            {error && (
              <div style={{
                padding: '10px 13px',
                background: 'var(--flag-bg)',
                border: '1px solid var(--flag-line)',
                borderRadius: 'var(--radius)',
                fontSize: '13px',
                color: 'var(--flag)',
                marginBottom: '16px',
              }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%', marginTop: '6px' }}>
              {loading ? (
                mode === 'login' ? 'Signing in...' : 'Creating firm...'
              ) : (
                mode === 'login' ? 'Sign in' : 'Create firm & sign in'
              )}
            </button>
          </form>

          <p className="login-foot">
            {mode === 'login' ? (
              <>New firm? <button onClick={() => { setMode('signup'); setError(''); }} style={{ background: 'none', border: 'none', borderBottom: '1px solid var(--line-strong)', color: 'inherit', font: 'inherit', cursor: 'pointer' }}>Create an account</button></>
            ) : (
              <>Already have an account? <button onClick={() => { setMode('login'); setError(''); }} style={{ background: 'none', border: 'none', borderBottom: '1px solid var(--line-strong)', color: 'inherit', font: 'inherit', cursor: 'pointer' }}>Sign in</button></>
            )}
          </p>

          <div className="demo-note" style={{ background: 'var(--slate-bg)', border: '1px solid var(--slate-line)', color: 'var(--ink-70)' }}>
            Sign in with your credentials to access the platform.
          </div>
        </div>
      </div>
    </div>
  );
}
