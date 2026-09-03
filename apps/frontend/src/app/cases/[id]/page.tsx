'use client';

import { useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

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

const STATUS_COLORS: Record<string, string> = {
  done: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  processing: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  queued: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
  error: 'bg-red-500/10 text-red-400 border-red-500/20',
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
    <div className="min-h-screen flex bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900/50 border-r border-slate-700/50 flex flex-col">
        <div className="p-5 border-b border-slate-700/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <span className="text-lg font-bold text-white tracking-tight">ClauseBridge</span>
          </div>
        </div>
        <nav className="flex-1 p-3">
          <ul className="space-y-1">
            <li>
              <Link href="/dashboard" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                </svg>
                Dashboard
              </Link>
            </li>
            <li>
              <Link href="/cases" className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-blue-600/10 text-blue-400 border border-blue-500/20">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                Cases
              </Link>
            </li>
          </ul>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-8 overflow-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
          <Link href="/cases" className="hover:text-slate-300 transition-colors">Cases</Link>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-slate-300">{caseDetail?.title || 'Loading...'}</span>
        </div>

        {/* Header */}
        <header className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white tracking-tight">{caseDetail?.title || 'Case'}</h1>
            <p className="text-slate-400 mt-1">
              {documents.length} document{documents.length !== 1 ? 's' : ''} uploaded
            </p>
          </div>
          <label className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium rounded-xl transition-all duration-200 shadow-lg shadow-blue-500/25 cursor-pointer">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            {uploading ? 'Uploading...' : 'Upload PDF'}
            <input
              type="file"
              accept=".pdf"
              onChange={handleUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </header>

        {uploadError && (
          <div className="mb-6 flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2.5">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            {uploadError}
          </div>
        )}

        {/* Documents List */}
        {documents.length === 0 ? (
          <div className="text-center py-20">
            <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700/50 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-slate-400 mb-2">No documents uploaded yet</p>
            <p className="text-slate-500 text-sm">Upload a PDF to start analysis</p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <Link
                key={doc.id}
                href={`/cases/${caseId}/documents/${doc.id}`}
                className="block bg-slate-800/50 border border-slate-700/50 rounded-xl p-5 hover:border-slate-600/50 hover:bg-slate-800/80 transition-all group"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center">
                      <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-white font-medium group-hover:text-blue-400 transition-colors">{doc.filename || 'Document'}</h3>
                      <p className="text-slate-500 text-sm mt-0.5">
                        {doc.document_type ? `Type: ${doc.document_type}` : 'Awaiting classification'}
                        {doc.classification_confidence ? ` (${(doc.classification_confidence * 100).toFixed(0)}% confidence)` : ''}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-1 text-xs font-medium rounded-full border ${STATUS_COLORS[doc.status] || STATUS_COLORS.queued}`}>
                      {doc.status}
                    </span>
                    <svg className="w-4 h-4 text-slate-500 group-hover:text-slate-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
