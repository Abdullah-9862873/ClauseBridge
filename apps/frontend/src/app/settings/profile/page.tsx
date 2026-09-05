'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { useToast } from '@/lib/toast-context';
import UserChip from '@/components/UserChip';

const API = 'http://localhost:8000';

export default function ProfilePage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      showToast({ message: 'New passwords do not match.', type: 'error' });
      return;
    }
    if (newPassword.length < 8) {
      showToast({ message: 'Password must be at least 8 characters.', type: 'error' });
      return;
    }
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`${API}/api/v1/auth/password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to change password');
      }
      showToast({ message: 'Password changed successfully.', type: 'success' });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      showToast({ message: err instanceof Error ? err.message : 'Failed to change password', type: 'error' });
    } finally {
      setLoading(false);
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
          <Link href="/cases" className="nav-item">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 4.5C2 3.67 2.67 3 3.5 3H6.5L8 4.5H12.5C13.33 4.5 14 5.17 14 6V11.5C14 12.33 13.33 13 12.5 13H3.5C2.67 13 2 12.33 2 11.5V4.5Z" stroke="currentColor" strokeWidth="1.3"/>
            </svg>
            Cases
          </Link>
        </nav>
        <div className="sidebar-spacer" />
        <UserChip />
      </aside>

      <div className="main-content">
        <div className="topbar">
          <div className="breadcrumb">
            <Link href="/dashboard" style={{ color: 'var(--ink-50)' }}>Dashboard</Link>
            <span style={{ color: 'var(--ink-35)' }}>/</span>
            <span className="seg-current">Profile</span>
          </div>
          <div className="topbar-actions">
            <Link href="/login" className="btn btn-ghost btn-sm" onClick={() => { localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token'); }}>Sign out</Link>
          </div>
        </div>

        <div className="screen">
          <div className="page-head">
            <div>
              <h2>Profile</h2>
              <p className="sub">Manage your account settings</p>
            </div>
          </div>

          <div className="card" style={{ maxWidth: '480px' }}>
            <div className="card-head">
              <h3>Account</h3>
            </div>
            <div style={{ padding: '16px 20px' }}>
              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '12px', color: 'var(--ink-50)', marginBottom: '4px' }}>Email</div>
                <div style={{ fontSize: '14px' }}>{user?.email || '—'}</div>
              </div>
              <Link href="/settings/firm" className="btn btn-ghost btn-sm" style={{ marginTop: '4px' }}>Firm settings</Link>
            </div>
          </div>

          <div className="card" style={{ maxWidth: '480px', marginTop: '20px' }}>
            <div className="card-head">
              <h3>Change password</h3>
            </div>
            <form onSubmit={handleChangePassword} style={{ padding: '16px 20px' }}>
              <div className="field">
                <label htmlFor="currentPassword">Current password</label>
                <input
                  id="currentPassword"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="newPassword">New password</label>
                <input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="confirmPassword">Confirm new password</label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: 'auto', marginTop: '4px' }}>
                {loading ? 'Saving...' : 'Change password'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
