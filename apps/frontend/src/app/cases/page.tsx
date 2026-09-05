'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useToast } from '@/lib/toast-context';

interface Case {
  id: string;
  title: string;
  status: string;
  created_at: string;
}

export default function CasesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { showToast } = useToast();
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<Case | null>(null);

  const fetchCases = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch('http://localhost:8000/api/v1/cases?limit=20', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setCases(data.items || []);
      }
    } catch {
      setError('Failed to load cases');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, []);

  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setShowCreate(true);
      router.replace('/cases');
    }
  }, [searchParams, router]);

  const handleDeleteRetry = useCallback(async (target: Case) => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`http://localhost:8000/api/v1/cases/${target.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 0 || res.ok || res.status === 404) {
        setCases((prev) => prev.filter((c) => c.id !== target.id));
      } else {
        throw new Error(`Failed: ${res.status}`);
      }
    } catch {
      setCases((prev) => {
        if (prev.some((c) => c.id === target.id)) return prev;
        return [...prev, target];
      });
      showToast({
        message: 'Failed to delete the case.',
        type: 'error',
        onRetry: () => handleDeleteRetry(target),
        onNavigate: () => router.push('/cases'),
        navigateLabel: 'Go to Cases',
      });
    }
  }, [showToast, router]);

  const handleDelete = () => {
    if (!deleteTarget) return;

    const target = deleteTarget;
    const index = cases.findIndex((c) => c.id === target.id);
    const snapshot = { item: target, index };

    setCases((prev) => prev.filter((c) => c.id !== target.id));
    setDeleteTarget(null);

    const token = localStorage.getItem('access_token');
    fetch(`http://localhost:8000/api/v1/cases/${target.id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => {
      if (res.status === 0 || res.ok || res.status === 404) return;
      throw new Error(`Failed: ${res.status}`);
    }).catch((err) => {
      console.error('Delete failed:', err);
      setCases((prev) => {
        if (prev.some((c) => c.id === target.id)) return prev;
        const copy = [...prev];
        copy.splice(snapshot.index, 0, snapshot.item);
        return copy;
      });
      showToast({
        message: 'Failed to delete the case.',
        type: 'error',
        onRetry: () => handleDeleteRetry(target),
        onNavigate: () => router.push('/cases'),
        navigateLabel: 'Go to Cases',
      });
    });
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError('');

    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch('http://localhost:8000/api/v1/cases', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title: newTitle }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to create case' }));
        throw new Error(err.detail || 'Failed to create case');
      }

      const newCase = await res.json();
      setCases([{ ...newCase, status: 'active', created_at: new Date().toISOString() }, ...cases]);
      setNewTitle('');
      setShowCreate(false);
    } catch {
      setError('Failed to create case');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <svg width="20" height="20" viewBox="0 0 26 26" fill="none">
            <path d="M4 21V6.5C4 5.12 5.12 4 6.5 4H15L22 11V19.5C22 20.88 20.88 22 19.5 22H6.5C5.12 22 4 20.88 4 19.5Z" stroke="#F7F6F1" strokeWidth="1.4"/>
            <path d="M15 4V9.5C15 10.33 15.67 11 16.5 11H22" stroke="#F7F6F1" strokeWidth="1.4"/>
            <line x1="8" y1="14.5" x2="17.5" y2="14.5" stroke="#B23B2E" strokeWidth="1.4"/>
            <line x1="8" y1="17.6" x2="14" y2="17.6" stroke="#F7F6F1" strokeWidth="1.4"/>
          </svg>
          Clausebridge
        </div>
        <nav className="sidebar-nav">
          <Link href="/dashboard" className="nav-item">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
              <rect x="9" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
              <rect x="2" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
              <rect x="9" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3"/>
            </svg>
            Dashboard
          </Link>
          <Link href="/cases" className="nav-item active">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 4.5C2 3.67 2.67 3 3.5 3H6.5L8 4.5H12.5C13.33 4.5 14 5.17 14 6V11.5C14 12.33 13.33 13 12.5 13H3.5C2.67 13 2 12.33 2 11.5V4.5Z" stroke="currentColor" strokeWidth="1.3"/>
            </svg>
            Cases
          </Link>
        </nav>
        <div className="sidebar-spacer" />
        <div className="user-chip">
          <div className="avatar">U</div>
          <div>
            <div className="name">User</div>
            <div className="role">Member</div>
          </div>
        </div>
      </aside>

      <div className="main-content">
        <div className="topbar">
          <div className="breadcrumb">
            <Link href="/dashboard" style={{ color: 'var(--ink-50)' }}>Dashboard</Link>
            <span style={{ color: 'var(--ink-35)' }}>/</span>
            <span className="seg-current">Cases</span>
          </div>
          <div className="topbar-actions">
            <Link href="/login" className="btn btn-ghost btn-sm" onClick={() => localStorage.removeItem('access_token')}>Sign out</Link>
          </div>
        </div>

        <div className="screen">
          <div className="page-head">
            <div>
              <h2>Cases</h2>
              <p className="sub">Manage your legal document cases</p>
            </div>
            <button onClick={() => setShowCreate(true)} className="btn btn-primary" style={{ width: 'auto', marginTop: 0 }}>
              New case
            </button>
          </div>

          {/* Create Case Modal */}
          {showCreate && (
            <div style={{
              position: 'fixed', inset: 0, background: 'rgba(22,33,44,0.4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
            }}>
              <div style={{
                background: 'var(--surface)', border: '1px solid var(--line)',
                borderRadius: 'var(--radius)', padding: '24px', width: '100%', maxWidth: '400px',
              }}>
                <h3 style={{ fontSize: '18px', marginBottom: '16px' }}>Create new case</h3>
                <form onSubmit={handleCreate}>
                  <div className="field">
                    <label htmlFor="caseTitle">Case title</label>
                    <input
                      id="caseTitle"
                      type="text"
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      placeholder="e.g. Acme Corp Contract Review"
                      required
                    />
                  </div>
                  {error && <p style={{ color: 'var(--flag)', fontSize: '13px', marginBottom: '12px' }}>{error}</p>}
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button type="button" onClick={() => setShowCreate(false)} className="btn btn-ghost" style={{ flex: 1 }}>
                      Cancel
                    </button>
                    <button type="submit" disabled={creating} className="btn btn-primary" style={{ flex: 1 }}>
                      {creating ? 'Creating...' : 'Create'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Cases List */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--ink-50)' }}>
              Loading cases...
            </div>
          ) : cases.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--ink-50)' }}>
              <p>No cases yet</p>
              <button onClick={() => setShowCreate(true)} style={{
                background: 'none', border: 'none', color: 'var(--brass)',
                fontSize: '13px', marginTop: '8px', cursor: 'pointer', borderBottom: '1px solid var(--brass-line)',
              }}>
                Create your first case
              </button>
            </div>
          ) : (
            <div className="card">
              <table>
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <tr key={c.id} className="row-link">
                      <td>
                        <Link href={`/cases/${c.id}`} style={{ display: 'block' }}>
                          <div className="cell-primary">{c.title}</div>
                        </Link>
                      </td>
                      <td><span className={`pill ${c.status === 'active' ? 'processing' : 'done'}`}>{c.status}</span></td>
                      <td>{new Date(c.created_at).toLocaleDateString()}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <Link href={`/cases/${c.id}`} className="btn btn-ghost btn-sm">View</Link>
                          <button
                            className="btn btn-ghost btn-sm"
                            style={{ color: 'var(--flag)' }}
                            onClick={(e) => {
                              e.preventDefault();
                              setDeleteTarget(c);
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {/* Delete Case Modal */}
          {deleteTarget && (
            <div className="modal-backdrop" onClick={() => setDeleteTarget(null)}>
              <div className="modal-box" onClick={(e) => e.stopPropagation()}>
                <h3>Delete case</h3>
                <p>
                  Delete <strong>{deleteTarget.title}</strong> and all its documents?
                  This cannot be undone.
                </p>
                <div className="modal-actions">
                  <button
                    onClick={() => setDeleteTarget(null)}
                    className="btn btn-ghost"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDelete}
                    className="btn btn-danger"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
