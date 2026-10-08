'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { authFetch } from './token-refresh';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

export function getReportUrl(caseId: string): string {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  return `${API}/api/v1/cases/${caseId}/report/pdf?token=${token}`;
}

export function useDocument(caseId: string, docId: string) {
  return useQuery<DocumentDetail>({
    queryKey: ['document', caseId, docId],
    queryFn: async () => {
      const res = await authFetch(`${API}/api/v1/cases/${caseId}/documents/${docId}`);
      if (!res.ok) throw new Error('Failed to fetch document');
      return res.json();
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'queued' || status === 'processing') return 2000;
      return false;
    },
  });
}

export function useClauses(caseId: string, docId: string) {
  return useQuery<{ items: Clause[] }>({
    queryKey: ['clauses', caseId, docId],
    queryFn: async () => {
      const res = await authFetch(`${API}/api/v1/cases/${caseId}/documents/${docId}/clauses?limit=100`);
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
      const res = await authFetch(`${API}/api/v1/dashboard/stats`);
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
  source: string;
  matched_reference: string | null;
  verified: boolean;
  created_at: string;
}

export function useAnomalies(
  caseId: string,
  docId: string,
  filters?: { severity?: string; reviewed?: boolean }
) {
  return useQuery<{ items: Anomaly[] }>({
    queryKey: ['anomalies', caseId, docId, filters],
    queryFn: async () => {
      const params = new URLSearchParams({ document_id: docId, limit: '100' });
      if (filters?.severity) params.set('severity', filters.severity);
      if (filters?.reviewed !== undefined) params.set('reviewed', String(filters.reviewed));
      const res = await authFetch(
        `${API}/api/v1/cases/${caseId}/anomalies?${params}`
      );
      if (!res.ok) throw new Error('Failed to fetch anomalies');
      return res.json();
    },
    placeholderData: (previousData) => previousData,
    staleTime: 5_000,
    // Auto-refetch anomalies every 5 seconds while document is processing
    refetchInterval: (query) => {
      const data = query.state.data;
      // If we have no anomalies yet and document might still be processing, keep checking
      if (!data || data.items.length === 0) return 5000;
      return false;
    },
  });
}

export function useMarkReviewed(caseId: string, docId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ anomalyId, reviewed }: { anomalyId: string; reviewed: boolean }) => {
      const res = await authFetch(
        `${API}/api/v1/cases/${caseId}/anomalies/${anomalyId}/review`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reviewed }),
        }
      );
      if (!res.ok) throw new Error('Failed to mark reviewed');
      return res.json();
    },
    onMutate: async ({ anomalyId, reviewed }) => {
      await queryClient.cancelQueries({ queryKey: ['anomalies', caseId, docId] });
      const previous = queryClient.getQueriesData<{ items: Anomaly[] }>({
        queryKey: ['anomalies', caseId, docId],
      });
      const filters: Array<{ severity?: string; reviewed?: boolean } | undefined> = [
        undefined,
        { severity: 'high' },
        { severity: 'medium' },
        { severity: 'low' },
        { reviewed: false },
      ];
      for (const filter of filters) {
        queryClient.setQueryData<{ items: Anomaly[] }>(
          ['anomalies', caseId, docId, filter],
          (old) => {
            if (!old) return old;
            const updated = old.items.map((a: Anomaly) =>
              a.id === anomalyId ? { ...a, reviewed } : a
            );
            if (!filter) return { items: updated };
            return {
              items: updated.filter((a: Anomaly) => {
                if (filter.severity) return a.severity === filter.severity;
                if (filter.reviewed !== undefined) return a.reviewed === filter.reviewed;
                return true;
              }),
            };
          }
        );
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        for (const [key, data] of context.previous) {
          queryClient.setQueryData(key, data);
        }
      }
    },
  });
}
