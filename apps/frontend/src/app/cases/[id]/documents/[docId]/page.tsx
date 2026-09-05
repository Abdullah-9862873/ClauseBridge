'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useQueryClient } from '@tanstack/react-query';
import { useDocument, useClauses, useAnomalies, useMarkReviewed, getPdfUrl } from '@/lib/hooks';
import type { Anomaly } from '@/lib/hooks';
import { PdfViewer, type PdfViewerHandle } from '@/components/PdfViewer';

const SEVERITY_SEV: Record<string, string> = {
  high: 'sev high',
  medium: 'sev medium',
  low: 'sev low',
};

const STATUS_PILL: Record<string, string> = {
  done: 'done',
  processing: 'processing',
  queued: 'queued',
  error: 'error',
};

export default function DocumentDetailPage() {
  const params = useParams();
  const caseId = params.id as string;
  const docId = params.docId as string;

  const [selectedClause, setSelectedClause] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [anomalyFilter, setAnomalyFilter] = useState<string>('all');
  const [zoom, setZoom] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const pdfViewerRef = useRef<PdfViewerHandle>(null);

  const { data: document, isLoading: docLoading } = useDocument(caseId, docId);
  const { data: clauseData, isLoading: clauseLoading } = useClauses(caseId, docId);
  const { data: allAnomalyData } = useAnomalies(caseId, docId, undefined);

  const queryClient = useQueryClient();
  useEffect(() => {
    if (!allAnomalyData || allAnomalyData.items.length === 0) return;
    const filters = [
      { severity: 'high' },
      { severity: 'medium' },
      { severity: 'low' },
      { reviewed: false },
    ];
    for (const f of filters) {
      queryClient.prefetchQuery({
        queryKey: ['anomalies', caseId, docId, f],
        queryFn: async () => {
          const params = new URLSearchParams({ document_id: docId, limit: '100' });
          if (f.severity) params.set('severity', f.severity);
          if (f.reviewed !== undefined) params.set('reviewed', String(f.reviewed));
          const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
          const res = await fetch(
            `http://localhost:8000/api/v1/cases/${caseId}/anomalies?${params}`,
            { headers: token ? { Authorization: `Bearer ${token}` } : {} }
          );
          if (!res.ok) throw new Error('Failed to fetch anomalies');
          return res.json();
        },
        staleTime: 60_000,
      });
    }
  }, [allAnomalyData, caseId, docId, queryClient]);
  const anomalyFilters = anomalyFilter === 'unreviewed'
    ? { reviewed: false }
    : anomalyFilter !== 'all'
      ? { severity: anomalyFilter }
      : undefined;
  const { data: anomalyData, isFetching: anomaliesLoading } = useAnomalies(
    caseId,
    docId,
    anomalyFilter === 'all' ? undefined : anomalyFilters
  );
  const markReviewed = useMarkReviewed(caseId, docId);
  const clauses = clauseData?.items || [];
  const anomalies = anomalyData?.items || [];
  const totalAnomalyCount = allAnomalyData?.items?.length ?? 0;
  const hasAnomalies = totalAnomalyCount > 0;

  const anomalyByClauseId = new Map<string, Anomaly>();
  for (const a of anomalies) {
    anomalyByClauseId.set(a.clause_id, a);
  }

  const status = document?.status || '';
  const isProcessing = status === 'queued' || status === 'processing';

  const searchText = searchInput.trim();

  const searchFilteredClauses = clauseLoading ? [] : clauses.filter((clause) => {
    if (!searchText) return true;
    const term = searchText.toLowerCase();
    return (
      clause.clause_text.toLowerCase().includes(term) ||
      clause.clause_type.toLowerCase().includes(term)
    );
  });

  const displayedClauses = searchFilteredClauses.filter((clause) => {
    const anomaly = anomalyByClauseId.get(clause.id);
    if (!anomaly) return false;
    if (anomalyFilter === 'all') return true;
    if (anomalyFilter === 'unreviewed') return !anomaly.reviewed;
    return anomaly.severity === anomalyFilter;
  });

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
            <Link href={`/cases/${caseId}`} style={{ color: 'var(--ink-50)' }}>Case</Link>
            <span style={{ color: 'var(--ink-35)' }}>/</span>
            <span className="seg-current">{document?.filename || 'Document'}</span>
          </div>
          <div className="topbar-actions">
            <Link href={`/cases/${caseId}`} className="btn btn-ghost btn-sm">Back to case</Link>
          </div>
        </div>

        <div className="screen">
          <div className="page-head">
            <div>
              <h2 style={{ fontSize: '20px' }}>{document?.filename || 'Document'}</h2>
              <p className="sub">
                {document?.document_type ? `${document.document_type}` : 'Awaiting classification'}
                {document?.classification_confidence ? ` (${(parseFloat(document.classification_confidence) * 100).toFixed(0)}% confidence)` : ''}
                {clauses.length > 0 ? ` \u00B7 ${clauses.length} clause${clauses.length !== 1 ? 's' : ''} found` : ''}
                {totalAnomalyCount > 0 ? ` \u00B7 ${totalAnomalyCount} anomal${totalAnomalyCount !== 1 ? 'ies' : 'y'}` : ''}
              </p>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <span className={`pill ${STATUS_PILL[status] || 'queued'}`}>{status || 'loading'}</span>
            </div>
          </div>

          <div className="viewer-grid">
            {/* Left: Document / PDF */}
            <div className="doc-page-wrap">
              {docLoading ? (
                <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--ink-50)' }}>
                  Loading document...
                </div>
              ) : isProcessing ? (
                <div style={{ textAlign: 'center', padding: '40px 0' }}>
                  <div style={{ color: 'var(--brass)', fontSize: '14px', fontWeight: 500, marginBottom: '6px' }}>
                    {status === 'queued' ? 'In queue...' : 'Processing document...'}
                  </div>
                  <div style={{ color: 'var(--ink-50)', fontSize: '13px' }}>
                    Extracting text and analyzing clauses
                  </div>
                </div>
              ) : status === 'done' ? (
                <PdfViewer
                  ref={pdfViewerRef}
                  url={getPdfUrl(caseId, docId)}
                  currentPage={currentPage}
                  onPageChange={setCurrentPage}
                  zoom={zoom}
                  onZoomChange={setZoom}
                  searchText={searchText}
                />
              ) : status === 'error' ? (
                <div style={{ textAlign: 'center', padding: '40px 0' }}>
                  <div style={{ color: 'var(--flag)', fontWeight: 500, marginBottom: '4px' }}>Processing failed</div>
                  <div style={{ color: 'var(--ink-50)', fontSize: '13px' }}>There was an error processing this document</div>
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--ink-50)' }}>
                  No document data
                </div>
              )}
            </div>

            {/* Right: Clause List */}
            <div className="clause-list">
              <div style={{ marginBottom: '4px' }}>
                <h3 style={{ fontSize: '16px', marginBottom: '2px' }}>Extracted Clauses</h3>
                <p style={{ fontSize: '12.5px', color: 'var(--ink-50)' }}>
                  {clauseLoading ? 'Loading...' : `${clauses.length} clause${clauses.length !== 1 ? 's' : ''} found`}
                </p>
              </div>

              {clauses.length > 0 && (
                <div className="search-wrap">
                  <svg className="search-icon" width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.3"/>
                    <line x1="10.2" y1="10.2" x2="14.5" y2="14.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                  </svg>
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Search clauses..."
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                  />
                  {searchInput && (
                    <button
                      className="search-clear"
                      onClick={() => setSearchInput('')}
                    >
                      ×
                    </button>
                  )}
                </div>
              )}

              {hasAnomalies && (
                <div className="filter-row">
                  {['all', 'high', 'medium', 'low', 'unreviewed'].map((f) => (
                    <button
                      key={f}
                      className={`chip ${anomalyFilter === f ? 'active' : ''}`}
                      onClick={() => setAnomalyFilter(f)}
                    >
                      {f === 'all' ? 'All' : f === 'unreviewed' ? 'Unreviewed' : f.charAt(0).toUpperCase() + f.slice(1)}
                    </button>
                  ))}
                  {anomaliesLoading && (
                    <span style={{ fontSize: '12px', color: 'var(--ink-50)', marginLeft: '4px' }}>Loading...</span>
                  )}
                </div>
              )}

              {clauseLoading ? (
                <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--ink-50)', fontSize: '13px' }}>
                  Loading clauses...
                </div>
              ) : clauses.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--ink-50)', fontSize: '13px' }}>
                  {status === 'done' ? 'No clauses extracted' : 'Clauses will appear after processing'}
                </div>
              ) : searchText && searchFilteredClauses.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--ink-50)', fontSize: '13px' }}>
                  No clauses matching &ldquo;{searchText}&rdquo;
                </div>
              ) : displayedClauses.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--ink-50)', fontSize: '13px' }}>
                  No anomalies matching this filter
                </div>
              ) : (
                displayedClauses.map((clause) => {
                  const anomaly = anomalyByClauseId.get(clause.id);
                  const isReviewed = anomaly?.reviewed ?? false;
                  return (
                    <div
                      key={clause.id}
                      onClick={() => {
                        const next = selectedClause === clause.id ? null : clause.id;
                        setSelectedClause(next);
                        if (next && clause.page_number) {
                          pdfViewerRef.current?.jumpToPage(clause.page_number);
                        }
                      }}
                      className={`clause-card ${selectedClause === clause.id ? 'active' : ''} ${isReviewed ? 'reviewed' : ''}`}
                      style={isReviewed ? { opacity: 0.6 } : {}}
                    >
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                        <span className="ctype">
                          {clause.clause_type}
                        </span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          {anomaly && (
                            <span
                              style={{
                                fontSize: '11px',
                                fontWeight: 700,
                                padding: '3px 9px',
                                borderRadius: '10px',
                                color: '#fff',
                                background: anomaly.severity === 'high' ? 'var(--flag)' : anomaly.severity === 'medium' ? 'var(--brass)' : 'var(--ok)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.4px',
                              }}
                            >
                              {anomaly.severity}
                            </span>
                          )}
                          {anomaly && (
                            <label
                              className="checkbox"
                              title={isReviewed ? 'Mark as unreviewed' : 'Mark as reviewed'}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <input
                                type="checkbox"
                                checked={isReviewed}
                                onChange={() => markReviewed.mutate({ anomalyId: anomaly.id, reviewed: !isReviewed })}
                                className="checkbox"
                              />
                            </label>
                          )}
                        </div>
                      </div>
                      <p className="csnip" style={selectedClause === clause.id ? {} : { display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {clause.clause_text}
                      </p>
                      {anomaly && (
                        <div className="cfoot">
                          <span className={SEVERITY_SEV[anomaly.severity] || 'sev low'}>
                            {anomaly.severity} anomaly
                          </span>
                          <div className="conf">
                            <div className="conf-bar">
                              <span style={{ width: `${anomaly.confidence * 100}%` }} />
                            </div>
                            <span className="num mono">
                              {anomaly.confidence.toFixed(2)}
                            </span>
                          </div>
                        </div>
                      )}
                      {anomaly && selectedClause === clause.id && (
                        <div className="anomaly-detail">
                          <div className="anomaly-detail-header">
                            <span className="anomaly-detail-title">Anomaly Detail</span>
                            <span
                              className="anomaly-detail-severity"
                              style={{
                                background: anomaly.severity === 'high' ? 'var(--flag)' : anomaly.severity === 'medium' ? 'var(--brass)' : 'var(--ok)',
                              }}
                            >
                              {anomaly.severity}
                            </span>
                          </div>
                          <div className="anomaly-detail-grid">
                            <div className="anomaly-detail-field">
                              <span className="anomaly-detail-label">Confidence</span>
                              <div className="anomaly-detail-confidence">
                                <div className="anomaly-detail-conf-bar">
                                  <span style={{ width: `${anomaly.confidence * 100}%` }} />
                                </div>
                                <span className="anomaly-detail-conf-num">{(anomaly.confidence * 100).toFixed(0)}%</span>
                              </div>
                            </div>
                            <div className="anomaly-detail-field">
                              <span className="anomaly-detail-label">Detected</span>
                              <span className="anomaly-detail-value">
                                {new Date(anomaly.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                              </span>
                            </div>
                          </div>
                          <div className="anomaly-detail-reason">
                            <span className="anomaly-detail-label">Reasoning</span>
                            <p>{anomaly.reasons}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
