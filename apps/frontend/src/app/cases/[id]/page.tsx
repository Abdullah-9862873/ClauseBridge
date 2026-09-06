'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAnomalies } from '@/lib/hooks';
import { useToast } from '@/lib/toast-context';
import UserChip from '@/components/UserChip';
import { authFetch } from '@/lib/token-refresh';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const COUNTRIES = [
  { code: 'IN', name: 'India', flag: '\u{1F1EE}\u{1F1F3}' },
  { code: 'US', name: 'United States', flag: '\u{1F1FA}\u{1F1F8}' },
  { code: 'UK', name: 'United Kingdom', flag: '\u{1F1EC}\u{1F1E7}' },
  { code: 'AE', name: 'United Arab Emirates', flag: '\u{1F1E6}\u{1F1EA}' },
  { code: 'SG', name: 'Singapore', flag: '\u{1F1F8}\u{1F1EC}' },
  { code: 'AU', name: 'Australia', flag: '\u{1F1E6}\u{1F1FA}' },
  { code: 'CA', name: 'Canada', flag: '\u{1F1E8}\u{1F1E6}' },
  { code: 'DE', name: 'Germany', flag: '\u{1F1E9}\u{1F1EA}' },
  { code: 'FR', name: 'France', flag: '\u{1F1EB}\u{1F1F7}' },
  { code: 'JP', name: 'Japan', flag: '\u{1F1EF}\u{1F1F5}' },
  { code: 'BR', name: 'Brazil', flag: '\u{1F1E7}\u{1F1F7}' },
  { code: 'ZA', name: 'South Africa', flag: '\u{1F1FF}\u{1F1E6}' },
  { code: 'NG', name: 'Nigeria', flag: '\u{1F1F3}\u{1F1EC}' },
  { code: 'SA', name: 'Saudi Arabia', flag: '\u{1F1F8}\u{1F1E6}' },
  { code: 'KR', name: 'South Korea', flag: '\u{1F1F0}\u{1F1F7}' },
  { code: 'CN', name: 'China', flag: '\u{1F1E8}\u{1F1F3}' },
  { code: 'IT', name: 'Italy', flag: '\u{1F1EE}\u{1F1F9}' },
  { code: 'ES', name: 'Spain', flag: '\u{1F1EA}\u{1F1F8}' },
  { code: 'NL', name: 'Netherlands', flag: '\u{1F1F3}\u{1F1F1}' },
  { code: 'CH', name: 'Switzerland', flag: '\u{1F1E8}\u{1F1ED}' },
  { code: 'MX', name: 'Mexico', flag: '\u{1F1F2}\u{1F1FD}' },
  { code: 'AR', name: 'Argentina', flag: '\u{1F1E6}\u{1F1F7}' },
  { code: 'EG', name: 'Egypt', flag: '\u{1F1EA}\u{1F1EC}' },
  { code: 'PH', name: 'Philippines', flag: '\u{1F1F5}\u{1F1ED}' },
  { code: 'MY', name: 'Malaysia', flag: '\u{1F1F2}\u{1F1FE}' },
  { code: 'TH', name: 'Thailand', flag: '\u{1F1F9}\u{1F1ED}' },
  { code: 'VN', name: 'Vietnam', flag: '\u{1F1FB}\u{1F1F3}' },
  { code: 'ID', name: 'Indonesia', flag: '\u{1F1EE}\u{1F1E9}' },
  { code: 'PK', name: 'Pakistan', flag: '\u{1F1F5}\u{1F1F0}' },
  { code: 'BD', name: 'Bangladesh', flag: '\u{1F1E7}\u{1F1E9}' },
  { code: 'KE', name: 'Kenya', flag: '\u{1F1F0}\u{1F1EA}' },
];

interface Document {
  id: string;
  filename: string;
  status: string;
  document_type: string | null;
  classification_confidence: number | null;
  country: string | null;
  created_at: string;
}

interface ReferenceDocument {
  id: string;
  filename: string;
  status: string;
  chunk_count: number;
  created_at: string;
}

interface CaseDetail {
  id: string;
  title: string;
  status: string;
  country: string | null;
  created_at: string;
}

const STATUS_PILL: Record<string, string> = {
  done: 'done',
  processing: 'processing',
  queued: 'queued',
  error: 'error',
};

function AnomalyBadge({ caseId, docId }: { caseId: string; docId: string }) {
  const { data } = useAnomalies(caseId, docId);
  const count = data?.items?.length ?? 0;
  if (count === 0) return null;
  return (
    <span style={{
      fontSize: '11px', fontWeight: 600, padding: '2px 8px',
      borderRadius: '10px', color: '#fff', background: 'var(--flag)',
      marginLeft: '8px',
    }}>
      {count} anomal{count !== 1 ? 'ies' : 'y'}
    </span>
  );
}

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = params.id as string;
  const router = useRouter();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [selectedCountry, setSelectedCountry] = useState('');
  const [countrySaved, setCountrySaved] = useState(false);

  const [refUploading, setRefUploading] = useState(false);
  const [refUploadError, setRefUploadError] = useState('');
  const refFileInputRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [localDocuments, setLocalDocuments] = useState<Document[] | null>(null);
  const [downloadStatus, setDownloadStatus] = useState('');
  const lastFileRef = useRef<File | null>(null);

  const { data: caseDetail, isError: caseError } = useQuery<CaseDetail>({
    queryKey: ['case', caseId],
    queryFn: async () => {
      const res = await authFetch(`${API}/api/v1/cases/${caseId}`);
      if (!res.ok) throw new Error('Failed');
      return res.json();
    },
  });

  // Auto-load country from case detail
  useEffect(() => {
    if (caseDetail?.country) {
      setSelectedCountry(caseDetail.country);
      setCountrySaved(true);
    }
  }, [caseDetail]);

  const { data: docData, isError: docsError, isLoading: docsLoading } = useQuery<{ items: Document[] }>({
    queryKey: ['documents', caseId],
    queryFn: async () => {
      const res = await authFetch(`${API}/api/v1/cases/${caseId}/documents`);
      if (!res.ok) throw new Error('Failed');
      return res.json();
    },
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      if (items?.some((d) => d.status === 'queued' || d.status === 'processing')) return 3000;
      return false;
    },
  });

  const { data: refData, refetch: refetchRefs } = useQuery<{ items: ReferenceDocument[] }>({
    queryKey: ['reference-documents', caseId],
    queryFn: async () => {
      const res = await authFetch(`${API}/api/v1/cases/${caseId}/reference-documents`);
      if (!res.ok) return { items: [] };
      return res.json();
    },
  });

  const documents = localDocuments ?? docData?.items ?? null;
  const refDocuments = refData?.items ?? [];

  const handleDeleteDocRetry = useCallback(async (target: Document) => {
    try {
      const res = await authFetch(`${API}/api/v1/cases/${caseId}/documents/${target.id}`, {
        method: 'DELETE',
      });
      if (res.status === 0 || res.ok || res.status === 404) {
        setLocalDocuments((prev) => (prev ?? []).filter((d) => d.id !== target.id));
        queryClient.invalidateQueries({ queryKey: ['documents', caseId] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
      } else {
        throw new Error(`Failed: ${res.status}`);
      }
    } catch {
      setLocalDocuments((prev) => {
        const current = prev ?? docData?.items ?? [];
        if (current.some((d) => d.id === target.id)) return current;
        return [...current, target];
      });
      showToast({
        message: 'Failed to delete the document.',
        type: 'error',
        onRetry: () => handleDeleteDocRetry(target),
        onNavigate: () => router.push(`/cases/${caseId}`),
        navigateLabel: 'Go to Case',
      });
    }
  }, [caseId, queryClient, showToast, router, docData]);

  const handleDeleteDoc = () => {
    if (!deleteTarget) return;

    const target = deleteTarget;
    const currentDocs = localDocuments ?? docData?.items ?? [];
    const index = currentDocs.findIndex((d) => d.id === target.id);
    const snapshot = { item: target, index };

    setLocalDocuments(currentDocs.filter((d) => d.id !== target.id));
    setDeleteTarget(null);

    authFetch(`${API}/api/v1/cases/${caseId}/documents/${target.id}`, {
      method: 'DELETE',
    }).then((res) => {
      if (res.status === 0 || res.ok || res.status === 404) {
        queryClient.invalidateQueries({ queryKey: ['documents', caseId] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
      } else {
        throw new Error(`Failed: ${res.status}`);
      }
    }).catch((err) => {
      console.error('Delete document failed:', err);
      setLocalDocuments((prev) => {
        const current = prev ?? docData?.items ?? [];
        if (current.some((d) => d.id === target.id)) return current;
        const copy = [...current];
        copy.splice(snapshot.index, 0, snapshot.item);
        return copy;
      });
      showToast({
        message: 'Failed to delete the document.',
        type: 'error',
        onRetry: () => handleDeleteDocRetry(target),
        onNavigate: () => router.push(`/cases/${caseId}`),
        navigateLabel: 'Go to Case',
      });
    });
  };

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      lastFileRef.current = file;

      if (file.type !== 'application/pdf') {
        setUploadError('Only PDF files are allowed');
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        setUploadError('File size must be under 10MB');
        return;
      }

      if (!selectedCountry) {
        setUploadError('Please select a country before uploading documents.');
        return;
      }

      setUploading(true);
      setUploadError('');

      try {
        const idempotencyKey = crypto.randomUUID();
        const formData = new FormData();
        formData.append('file', file);
        formData.append('country', selectedCountry);

        const res = await authFetch(`${API}/api/v1/cases/${caseId}/documents`, {
          method: 'POST',
          headers: {
            'Idempotency-Key': idempotencyKey,
          },
          body: formData,
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to upload');
        }

        setLocalDocuments(null);
        queryClient.invalidateQueries({ queryKey: ['documents', caseId] });
        e.target.value = '';
        showToast({ message: 'Document uploaded successfully.', type: 'success' });
      } catch (err: unknown) {
        setUploadError(err instanceof Error ? err.message : 'Upload failed');
      } finally {
        setUploading(false);
      }
    },
    [caseId, queryClient, selectedCountry]
  );

  const handleRetryUpload = useCallback(() => {
    const file = lastFileRef.current;
    if (!file) return;
    setUploadError('');
    setUploading(true);
    const syntheticEvent = { target: { files: [file] } } as unknown as React.ChangeEvent<HTMLInputElement>;
    handleUpload(syntheticEvent);
  }, [handleUpload]);

  const handleRefUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0) return;

      setRefUploading(true);
      setRefUploadError('');

      try {
        for (let i = 0; i < files.length; i++) {
          const file = files[i];
          if (file.type !== 'application/pdf') {
            setRefUploadError(`${file.name} is not a PDF. Only PDF files are allowed.`);
            continue;
          }
          const formData = new FormData();
          formData.append('file', file);
          const res = await authFetch(`${API}/api/v1/cases/${caseId}/reference-documents`, {
            method: 'POST',
            body: formData,
          });
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || `Failed to upload ${file.name}`);
          }
        }
        refetchRefs();
        showToast({ message: 'Reference document(s) uploaded successfully.', type: 'success' });
        if (refFileInputRef.current) refFileInputRef.current.value = '';
      } catch (err: unknown) {
        setRefUploadError(err instanceof Error ? err.message : 'Upload failed');
      } finally {
        setRefUploading(false);
      }
    },
    [caseId, refetchRefs, showToast]
  );

  const handleDeleteRef = useCallback(
    async (refId: string) => {
      try {
        await authFetch(`${API}/api/v1/cases/${caseId}/reference-documents/${refId}`, {
          method: 'DELETE',
        });
        refetchRefs();
      } catch {
        showToast({ message: 'Failed to delete reference document.', type: 'error' });
      }
    },
    [caseId, refetchRefs, showToast]
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
        <UserChip />
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
            <Link href="/login" className="btn btn-ghost btn-sm" onClick={() => { localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token'); }}>Sign out</Link>
          </div>
        </div>

        <div className="screen">
          <div className="page-head">
            <div>
              <h2>{caseDetail?.title || 'Case'}</h2>
              <div className="case-meta">
                <div className="item">
                  <span>Documents</span>
                  {documents !== null ? documents.length : '\u2014'}
                </div>
              </div>
            </div>
          </div>

          {/* ===== SECTION 1: COUNTRY + REFERENCE DOCS ===== */}
          <div className="card" style={{ marginBottom: '20px' }}>
            <div className="card-head">
              <h3>Analysis Settings</h3>
            </div>
            <div style={{ padding: '20px' }}>
              {/* Country Selection */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--ink)', marginBottom: '6px' }}>
                  Country <span style={{ color: 'var(--flag)', fontSize: '12px' }}>*required</span>
                </label>
                <p style={{ fontSize: '12px', color: 'var(--ink-50)', margin: '0 0 8px 0' }}>
                  Select the country whose laws should be checked against your documents.
                </p>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {COUNTRIES.map((c) => (
                    <button
                      key={c.code}
                      onClick={() => {
                        setSelectedCountry(c.code);
                        setCountrySaved(false);
                      }}
                      style={{
                        padding: '8px 14px',
                        borderRadius: 'var(--radius)',
                        border: selectedCountry === c.code ? '2px solid var(--ink)' : '1px solid var(--ink-20)',
                        background: selectedCountry === c.code ? 'var(--ink)' : 'transparent',
                        color: selectedCountry === c.code ? '#fff' : 'var(--ink)',
                        cursor: 'pointer',
                        fontSize: '13px',
                        fontWeight: selectedCountry === c.code ? 600 : 400,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <span>{c.flag}</span>
                      {c.name}
                    </button>
                  ))}
                </div>
                {selectedCountry && !countrySaved && (
                  <button
                    onClick={async () => {
                      try {
                        const res = await authFetch(`${API}/api/v1/cases/${caseId}`, {
                          method: 'PATCH',
                          headers: {
                            'Content-Type': 'application/json',
                          },
                          body: JSON.stringify({ country: selectedCountry }),
                        });
                        if (res.ok) {
                          setCountrySaved(true);
                          queryClient.invalidateQueries({ queryKey: ['case', caseId] });
                          showToast({ message: 'Country saved successfully.', type: 'success' });
                        } else {
                          showToast({ message: 'Failed to save country.', type: 'error' });
                        }
                      } catch {
                        showToast({ message: 'Failed to save country.', type: 'error' });
                      }
                    }}
                    style={{
                      marginTop: '10px', padding: '6px 16px', borderRadius: 'var(--radius)',
                      border: 'none', background: 'var(--accent)', color: '#fff',
                      fontSize: '12px', fontWeight: 600, cursor: 'pointer',
                    }}
                  >
                    Save Country Selection
                  </button>
                )}
                {countrySaved && (
                  <span style={{ marginTop: '10px', display: 'block', fontSize: '12px', color: 'var(--accent)', fontWeight: 500 }}>
                    \u2713 Country saved — documents will be analyzed against {COUNTRIES.find((c) => c.code === selectedCountry)?.name} laws
                  </span>
                )}
              </div>

              {/* Reference Documents */}
              <div style={{ borderTop: '1px solid var(--ink-20)', paddingTop: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--ink)', marginBottom: '6px' }}>
                  Reference Documents <span style={{ color: 'var(--ink-35)', fontSize: '12px', fontWeight: 400 }}>(optional)</span>
                </label>
                <p style={{ fontSize: '12px', color: 'var(--ink-50)', margin: '0 0 10px 0', lineHeight: 1.5 }}>
                  Upload legal documents (law books, contracts, policies) that you want your documents checked against.
                  The system will prioritize findings from these reference documents over general country law knowledge.
                  <br />
                  <strong>How it works:</strong> Your reference documents are read and embedded. When analyzing a contract,
                  the system first checks each clause against your uploaded references, then checks against {selectedCountry ? COUNTRIES.find((c) => c.code === selectedCountry)?.name + '\'s' : 'the selected country\'s'} freely available laws.
                </p>

                {refDocuments.length > 0 && (
                  <div style={{ marginBottom: '10px' }}>
                    {refDocuments.map((ref) => (
                      <div key={ref.id} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '8px 12px', borderRadius: 'var(--radius)',
                        border: '1px solid var(--ink-20)', marginBottom: '6px', fontSize: '13px',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', background: 'var(--accent-bg)', color: 'var(--accent)' }}>
                            REF
                          </span>
                          {ref.filename}
                          {ref.status === 'done' && (
                            <span style={{ fontSize: '11px', color: 'var(--ink-35)' }}>
                              ({ref.chunk_count} chunks embedded)
                            </span>
                          )}
                          {ref.status !== 'done' && (
                            <span style={{ fontSize: '11px', color: 'var(--ink-35)' }}>
                              ({ref.status})
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => handleDeleteRef(ref.id)}
                          style={{
                            background: 'none', border: 'none', color: 'var(--flag)',
                            cursor: 'pointer', fontSize: '12px', padding: '2px 6px',
                          }}
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <label className="btn btn-ghost btn-sm" style={{ cursor: 'pointer', width: 'auto' }}>
                    {refUploading ? 'Uploading...' : 'Add Reference PDFs'}
                    <input
                      ref={refFileInputRef}
                      type="file"
                      accept=".pdf"
                      multiple
                      onChange={handleRefUpload}
                      disabled={refUploading}
                      style={{ display: 'none' }}
                    />
                  </label>
                  <span style={{ fontSize: '12px', color: 'var(--ink-35)' }}>PDF files up to 10MB each</span>
                </div>
                {refUploadError && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--flag)' }}>
                    {refUploadError}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ===== SECTION 2: DOCUMENT UPLOAD + TABLE (existing) ===== */}
          {uploadError && (
            <div style={{
              padding: '10px 13px', background: 'var(--flag-bg)',
              border: '1px solid var(--flag-line)', borderRadius: 'var(--radius)',
              fontSize: '13px', color: 'var(--flag)', marginBottom: '20px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px',
            }}>
              <span>{uploadError}</span>
              <button
                onClick={handleRetryUpload}
                style={{
                  background: 'none', border: '1px solid var(--flag-line)',
                  color: 'var(--flag)', borderRadius: '4px', padding: '3px 10px',
                  fontSize: '12px', cursor: 'pointer', whiteSpace: 'nowrap',
                }}
              >
                Retry
              </button>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginBottom: '12px' }}>
            {documents && documents.length > 0 && (() => {
              const allDone = documents.every((d) => d.status === 'done');
              const anyProcessing = documents.some((d) => d.status === 'queued' || d.status === 'processing');
              return (
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={!!downloadStatus || anyProcessing}
                  title={anyProcessing ? 'Wait for document processing to complete' : undefined}
                  onClick={async () => {
                  try {
                    setDownloadStatus('Fetching details...');
                    await new Promise((r) => setTimeout(r, 400));
                    setDownloadStatus('Compiling document...');
                    const res = await authFetch(`${API}/api/v1/cases/${caseId}/report/pdf`);
                    if (!res.ok) throw new Error(`Failed: ${res.status}`);
                    setDownloadStatus('Downloading...');
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'clausebridge-report.pdf';
                    a.click();
                    URL.revokeObjectURL(url);
                    await new Promise((r) => setTimeout(r, 500));
                  } catch {
                    showToast({ message: 'Failed to download report.', type: 'error' });
                  } finally {
                    setDownloadStatus('');
                  }
                }}
              >
                {downloadStatus || (anyProcessing ? 'Processing...' : 'Download Report')}
              </button>
              );
            })()}
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

          <div className="dropzone">
            <strong>Drop files to add to this case</strong> &mdash; or click &ldquo;Upload PDF&rdquo; above. PDF files up to 10MB.
          </div>

          <div className="card">
            <div className="card-head">
              <h3>Documents</h3>
            </div>
            {(() => {
              if (caseError || docsError) {
                return (
                  <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--flag)', fontSize: '13.5px' }}>
                    Failed to load data. <button onClick={() => window.location.reload()} style={{ background: 'none', border: 'none', color: 'var(--flag)', textDecoration: 'underline', cursor: 'pointer' }}>Reload page</button>
                  </div>
                );
              }
              if (docsLoading) {
                return (
                  <div style={{ padding: '40px 20px', textAlign: 'center' }}>
                    <div className="spinner" style={{ margin: '0 auto 12px' }} />
                    <span style={{ color: 'var(--ink-50)', fontSize: '13.5px' }}>Loading documents...</span>
                  </div>
                );
              }
              if (!documents || documents.length === 0) {
                return (
                  <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--ink-50)', fontSize: '13.5px' }}>
                    No documents uploaded yet. Select a country above, then upload a PDF to start analysis.
                  </div>
                );
              }
              return (
                <table>
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Type</th>
                      <th>Country</th>
                      <th>Status</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((doc) => (
                      <tr key={doc.id}>
                        <td>
                          <div className="cell-primary" style={{ display: 'flex', alignItems: 'center' }}>
                            {doc.filename || 'Document'}
                            {doc.status === 'done' && <AnomalyBadge caseId={caseId} docId={doc.id} />}
                          </div>
                        </td>
                        <td>{doc.document_type || 'Awaiting classification'}</td>
                        <td>
                          {doc.country ? (
                            <span style={{ fontSize: '12px' }}>
                              {COUNTRIES.find((c) => c.code === doc.country)?.flag} {doc.country}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--ink-35)', fontSize: '12px' }}>\u2014</span>
                          )}
                        </td>
                        <td>
                          <span className={`pill ${STATUS_PILL[doc.status] || 'queued'}`}>
                            {doc.status}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            {doc.status === 'done' ? (
                              <Link href={`/cases/${caseId}/documents/${doc.id}`} className="btn btn-ghost btn-sm">View</Link>
                            ) : (
                              <span className="btn btn-ghost btn-sm" style={{ opacity: 0.4, pointerEvents: 'none' }}>View</span>
                            )}
                            <button
                              className="btn btn-ghost btn-sm"
                              style={{ color: 'var(--flag)' }}
                              onClick={() => setDeleteTarget(doc)}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()}
          </div>

          {/* Delete Document Modal */}
          {deleteTarget && (
            <div className="modal-backdrop" onClick={() => setDeleteTarget(null)}>
              <div className="modal-box" onClick={(e) => e.stopPropagation()}>
                <h3>Delete document</h3>
                <p>
                  Delete <strong>{deleteTarget.filename}</strong>?
                  All clauses and anomalies will be removed. This cannot be undone.
                </p>
                <div className="modal-actions">
                  <button
                    onClick={() => setDeleteTarget(null)}
                    className="btn btn-ghost"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteDoc}
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
