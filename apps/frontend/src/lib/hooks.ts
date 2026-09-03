'use client';

import { useQuery } from '@tanstack/react-query';

const API = 'http://localhost:8000';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface DocumentDetail {
  id: string;
  filename: string;
  status: string;
  document_type: string | null;
  classification_confidence: string | null;
  storage_url: string;
  created_at: string;
}

export interface Clause {
  id: string;
  clause_text: string;
  clause_type: string;
  page_number: number;
  created_at: string;
}

export function getPdfUrl(caseId: string, docId: string): string {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  return `${API}/api/v1/cases/${caseId}/documents/${docId}/pdf?token=${token}`;
}

export function useDocument(caseId: string, docId: string) {
  return useQuery<DocumentDetail>({
    queryKey: ['document', caseId, docId],
    queryFn: async () => {
      const res = await fetch(`${API}/api/v1/cases/${caseId}/documents/${docId}`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error('Failed to fetch document');
      return res.json();
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'queued' || status === 'processing') return 3000;
      return false;
    },
  });
}

export function useClauses(caseId: string, docId: string) {
  return useQuery<{ items: Clause[] }>({
    queryKey: ['clauses', caseId, docId],
    queryFn: async () => {
      const res = await fetch(`${API}/api/v1/cases/${caseId}/documents/${docId}/clauses?limit=100`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error('Failed to fetch clauses');
      return res.json();
    },
    refetchInterval: (query) => {
      const docQuery = query.state.data;
      if (!docQuery || (docQuery as unknown as { items: Clause[] }).items?.length === 0) return 5000;
      return false;
    },
  });
}

export interface DashboardStats {
  total_cases: number;
  total_documents: number;
  anomalies_detected: number;
}

export function useStats() {
  return useQuery<DashboardStats>({
    queryKey: ['stats'],
    queryFn: async () => {
      const res = await fetch(`${API}/api/v1/dashboard/stats`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error('Failed to fetch stats');
      return res.json();
    },
  });
}

export interface Anomaly {
  id: string;
  clause_id: string;
  severity: string;
  reasons: string;
  confidence: number;
  reviewed: boolean;
  created_at: string;
}

export function useAnomalies(caseId: string, docId: string) {
  return useQuery<{ items: Anomaly[] }>({
    queryKey: ['anomalies', caseId, docId],
    queryFn: async () => {
      const res = await fetch(
        `${API}/api/v1/cases/${caseId}/anomalies?document_id=${docId}&limit=100`,
        { headers: authHeaders() }
      );
      if (!res.ok) throw new Error('Failed to fetch anomalies');
      return res.json();
    },
  });
}
