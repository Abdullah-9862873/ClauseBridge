'use client';

import { useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';

const API = 'http://localhost:8000';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

interface Document {
  id: string;
  filename: string;
  status: string;
  document_type: string | null;
  classification_confidence: number | null;
  created_at: string;
}

interface CaseDetail {
  id: string;
  title: string;
  status: string;
  created_at: string;
}

const STATUS_PILL: Record<string, string> = {
  done: 'done',
  processing: 'processing',
  queued: 'queued',
  error: 'error',
};

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = params.id as string;
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const { data: caseDetail } = useQuery<CaseDetail>({
    queryKey: ['case', caseId],
    queryFn: async () => {
      const res = await fetch(`${API}/api/v1/cases/${caseId}`, { headers: authHeaders() });
      if (!res.ok) throw new Error('Failed');
      return res.json();
    },
  });

  const { data: docData } = useQuery<{ items: Document[] }>({
    queryKey: ['documents', caseId],
    queryFn: async () => {
      const res = await fetch(`${API}/api/v1/cases/${caseId}/documents`, { headers: authHeaders() });
      if (!res.ok) throw new Error('Failed');
      return res.json();
    },
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      if (items?.some((d) => d.status === 'queued' || d.status === 'processing')) return 3000;
      return false;
    },
  });

  const documents = docData?.items || [];

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      if (file.type !== 'application/pdf') {
        setUploadError('Only PDF files are allowed');
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        setUploadError('File size must be under 10MB');
        return;
      }

      setUploading(true);
      setUploadError('');

      try {
        const token = localStorage.getItem('access_token');
        const idempotencyKey = crypto.randomUUID();
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(`${API}/api/v1/cases/${caseId}/documents`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Idempotency-Key': idempotencyKey,
          },
          body: formData,
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to upload');
        }

        queryClient.invalidateQueries({ queryKey: ['documents', caseId] });
        e.target.value = '';
      } catch (err: unknown) {
        setUploadError(err instanceof Error ? err.message : 'Upload failed');
      } finally {
        setUploading(false);
      }
    },
    [caseId, queryClient]
  );

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
            <Link href="/cases" style={{ color: 'var(--ink-50)' }}>Cases</Link>
            <span style={{ color: 'var(--ink-35)' }}>/</span>
            <span className="seg-current">{caseDetail?.title || 'Case'}</span>
          </div>
          <div className="topbar-actions">
            <Link href="/login" className="btn btn-ghost btn-sm">Sign out</Link>
          </div>
        </div>

        <div className="screen">
          <div className="page-head">
            <div>
              <h2>{caseDetail?.title || 'Case'}</h2>
              <div className="case-meta">
                <div className="item">
                  <span>Documents</span>
                  {documents.length}
                </div>
              </div>
            </div>
            <label className="btn btn-primary" style={{ width: 'auto', marginTop: 0, cursor: 'pointer' }}>
              {uploading ? 'Uploading...' : 'Upload PDF'}
              <input
                type="file"
                accept=".pdf"
                onChange={handleUpload}
                disabled={uploading}
                style={{ display: 'none' }}
              />
            </label>
          </div>

          {uploadError && (
            <div style={{
              padding: '10px 13px', background: 'var(--flag-bg)',
              border: '1px solid var(--flag-line)', borderRadius: 'var(--radius)',
              fontSize: '13px', color: 'var(--flag)', marginBottom: '20px',
            }}>
              {uploadError}
            </div>
          )}

          <div className="dropzone">
            <strong>Drop files to add to this case</strong> &mdash; or click &ldquo;Upload PDF&rdquo; above. PDF files up to 10MB.
          </div>

          <div className="card">
            <div className="card-head">
              <h3>Documents</h3>
            </div>
            {documents.length === 0 ? (
              <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--ink-50)', fontSize: '13.5px' }}>
                No documents uploaded yet. Upload a PDF to start analysis.
              </div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <tr key={doc.id}>
                      <td>
                        <div className="cell-primary">{doc.filename || 'Document'}</div>
                      </td>
                      <td>{doc.document_type || 'Awaiting classification'}</td>
                      <td>
                        <span className={`pill ${STATUS_PILL[doc.status] || 'queued'}`}>
                          {doc.status}
                        </span>
                      </td>
                      <td>
                        {doc.status === 'done' ? (
                          <Link href={`/cases/${caseId}/documents/${doc.id}`} className="btn btn-ghost btn-sm">View</Link>
                        ) : (
                          <span className="btn btn-ghost btn-sm" style={{ opacity: 0.4, pointerEvents: 'none' }}>View</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
