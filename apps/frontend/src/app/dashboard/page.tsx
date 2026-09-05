'use client';

import Link from 'next/link';
import { useStats } from '@/lib/hooks';

export default function DashboardPage() {
  const { data: stats } = useStats();

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
          <Link href="/dashboard" className="nav-item active">
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
            <span className="seg-current">Dashboard</span>
          </div>
          <div className="topbar-actions">
            <Link href="/login" className="btn btn-ghost btn-sm">Sign out</Link>
          </div>
        </div>

        <div className="screen">
          <div className="page-head">
            <div>
              <h2>Dashboard</h2>
              <p className="sub">Overview of your legal document analysis</p>
            </div>
            <Link href="/cases" className="btn btn-primary" style={{ width: 'auto', marginTop: 0 }}>New case</Link>
          </div>

          <div className="stats-grid">
            <div className="stat-card">
              <div className="label">Active cases</div>
              <div className="value">{stats?.total_cases ?? 0}</div>
            </div>
            <div className="stat-card">
              <div className="label">Documents processed</div>
              <div className="value">{stats?.total_documents ?? 0}</div>
            </div>
            <div className="stat-card">
              <div className="label">Anomalies flagged</div>
              <div className="value flag-color">{stats?.anomalies_detected ?? 0}</div>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3>Quick actions</h3>
            </div>
            <div style={{ padding: '16px 20px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <Link href="/cases" className="btn btn-ghost btn-sm">View cases</Link>
              <Link href="/cases" className="btn btn-ghost btn-sm">New case</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
