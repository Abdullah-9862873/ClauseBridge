'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { useDocument, useClauses, useAnomalies, getPdfUrl } from '@/lib/hooks';
import type { Anomaly } from '@/lib/hooks';

const ReactPDF = dynamic(() => import('react-pdf').then(mod => mod.Document), { ssr: false });
const ReactPDFPage = dynamic(() => import('react-pdf').then(mod => mod.Page), { ssr: false });
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

const STATUS_COLORS: Record<string, string> = {
  done: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  processing: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  queued: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
  error: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const CLAUSE_COLORS: Record<string, string> = {
  termination: 'bg-red-500/10 text-red-400 border-red-500/20',
  liability: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  confidentiality: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  payment: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  dispute_resolution: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  intellectual_property: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
};

const SEVERITY_COLORS: Record<string, string> = {
  high: 'bg-red-500/15 text-red-400 border-red-500/30',
  medium: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  low: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
};

export default function DocumentDetailPage() {
  const params = useParams();
  const caseId = params.id as string;
  const docId = params.docId as string;

  const [selectedClause, setSelectedClause] = useState<string | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    import('react-pdf').then(({ pdfjs }) => {
      pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
    });
  }, []);

  const { data: document, isLoading: docLoading } = useDocument(caseId, docId);
  const { data: clauseData, isLoading: clauseLoading } = useClauses(caseId, docId);
  const { data: anomalyData } = useAnomalies(caseId, docId);
  const clauses = clauseData?.items || [];
  const anomalies = anomalyData?.items || [];

  const anomalyByClauseId = new Map<string, Anomaly>();
  for (const a of anomalies) {
    anomalyByClauseId.set(a.clause_id, a);
  }

  const status = document?.status || '';
  const isProcessing = status === 'queued' || status === 'processing';

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
      <main className="flex-1 flex overflow-hidden">
        {/* Left: PDF Viewer / Status */}
        <div className="flex-1 flex flex-col border-r border-slate-700/50">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm text-slate-500 p-4 border-b border-slate-700/50">
            <Link href="/cases" className="hover:text-slate-300 transition-colors">Cases</Link>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            <Link href={`/cases/${caseId}`} className="hover:text-slate-300 transition-colors">Case</Link>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            <span className="text-slate-300">{document?.filename || 'Document'}</span>
          </div>

          {/* Document Info */}
          <div className="p-6 border-b border-slate-700/50">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-white">{document?.filename || 'Document'}</h1>
                <p className="text-slate-400 mt-1">
                  {document?.document_type ? `Type: ${document.document_type}` : 'Awaiting classification'}
                  {document?.classification_confidence ? ` (${(parseFloat(document.classification_confidence) * 100).toFixed(0)}% confidence)` : ''}
                </p>
              </div>
              <span className={`px-3 py-1.5 text-sm font-medium rounded-full border ${STATUS_COLORS[status] || STATUS_COLORS.queued}`}>
                {status || 'loading'}
              </span>
            </div>
          </div>

          {/* PDF Viewer / Status */}
          <div className="flex-1 overflow-auto bg-slate-900/30 flex flex-col items-center">
            {docLoading ? (
              <div className="flex items-center justify-center py-20">
                <svg className="animate-spin w-8 h-8 text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              </div>
            ) : isProcessing ? (
              <div className="flex items-center justify-center py-20">
                <div className="text-center">
                  <svg className="animate-spin w-12 h-12 text-amber-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <p className="text-amber-400 font-medium">
                    {status === 'queued' ? 'In queue...' : 'Processing document...'}
                  </p>
                  <p className="text-slate-500 text-sm mt-1">
                    {status === 'queued' ? 'Waiting to be processed' : 'Extracting text and analyzing clauses'}
                  </p>
                </div>
              </div>
            ) : document?.status === 'done' ? (
              <div className="py-6 px-4 flex flex-col items-center">
                <ReactPDF
                  file={getPdfUrl(caseId, docId)}
                  onLoadSuccess={({ numPages: n }) => setNumPages(n)}
                  loading={
                    <div className="flex items-center justify-center py-20">
                      <svg className="animate-spin w-8 h-8 text-blue-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    </div>
                  }
                  error={
                    <div className="text-center py-20">
                      <p className="text-red-400">Failed to load PDF</p>
                    </div>
                  }
                >
                  <ReactPDFPage
                    pageNumber={currentPage}
                    width={Math.min(800, typeof window !== 'undefined' ? window.innerWidth - 420 : 800)}
                    className="shadow-lg shadow-black/20 rounded-lg overflow-hidden"
                  />
                </ReactPDF>
                {numPages > 1 && (
                  <div className="flex items-center gap-4 mt-4">
                    <button
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage <= 1}
                      className="px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    >
                      Previous
                    </button>
                    <span className="text-sm text-slate-400">
                      Page {currentPage} of {numPages}
                    </span>
                    <button
                      onClick={() => setCurrentPage(p => Math.min(numPages, p + 1))}
                      disabled={currentPage >= numPages}
                      className="px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                    >
                      Next
                    </button>
                  </div>
                )}
              </div>
            ) : status === 'error' ? (
              <div className="text-center py-20">
                <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
                <p className="text-red-400 font-medium">Processing failed</p>
                <p className="text-slate-500 text-sm mt-1">There was an error processing this document</p>
              </div>
            ) : (
              <div className="text-center py-20">
                <p className="text-slate-400">No document data</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: Clause Panel */}
        <div className="w-96 flex flex-col bg-slate-900/30">
          <div className="p-4 border-b border-slate-700/50">
            <h2 className="text-lg font-semibold text-white">Extracted Clauses</h2>
            <p className="text-slate-500 text-sm mt-0.5">{clauses.length} clause{clauses.length !== 1 ? 's' : ''} found</p>
          </div>

          <div className="flex-1 overflow-auto p-4 space-y-3">
            {clauseLoading ? (
              <div className="flex items-center justify-center py-10">
                <svg className="animate-spin w-6 h-6 text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              </div>
            ) : clauses.length === 0 ? (
              <div className="text-center py-10">
                <p className="text-slate-500 text-sm">
                  {status === 'done' ? 'No clauses extracted' : 'Clauses will appear after processing'}
                </p>
              </div>
            ) : (
              clauses.map((clause) => {
                const anomaly = anomalyByClauseId.get(clause.id);
                return (
                <div
                  key={clause.id}
                  onClick={() => setSelectedClause(selectedClause === clause.id ? null : clause.id)}
                  className={`bg-slate-800/50 border rounded-xl p-4 cursor-pointer transition-all ${
                    selectedClause === clause.id
                      ? 'border-blue-500/50 bg-blue-500/5'
                      : anomaly
                        ? 'border-amber-500/30 hover:border-amber-500/50'
                        : 'border-slate-700/50 hover:border-slate-600/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${CLAUSE_COLORS[clause.clause_type] || 'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>
                        {clause.clause_type}
                      </span>
                      {anomaly && (
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${SEVERITY_COLORS[anomaly.severity] || SEVERITY_COLORS.low}`}>
                          {anomaly.severity} anomaly
                        </span>
                      )}
                    </div>
                    <span className="text-slate-500 text-xs">Page {clause.page_number}</span>
                  </div>
                  <p className={`text-sm leading-relaxed ${
                    selectedClause === clause.id ? 'text-slate-200' : 'text-slate-400 line-clamp-3'
                  }`}>
                    {clause.clause_text}
                  </p>
                  {anomaly && selectedClause === clause.id && (
                    <div className="mt-3 pt-3 border-t border-slate-700/50">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-amber-400">Anomaly Reason:</span>
                        <span className="text-xs text-slate-400">{(anomaly.confidence * 100).toFixed(0)}% confidence</span>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed">{anomaly.reasons}</p>
                    </div>
                  )}
                </div>
                );
              })
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
