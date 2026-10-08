const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let refreshTimer: ReturnType<typeof setTimeout> | null = null;
let refreshPromise: Promise<boolean> | null = null;

function parseJwtExp(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return typeof payload.exp === 'number' ? payload.exp : null;
  } catch {
    return null;
  }
}

async function doRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    scheduleRefresh(data.access_token);
    return true;
  } catch {
    return false;
  }
}

function ensureRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function authFetch(
  input: RequestInfo,
  init?: RequestInit
): Promise<Response> {
  const token = localStorage.getItem('access_token');
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let res: Response;
  try {
    res = await fetch(input, { ...init, headers });
  } catch {
    return Response.error();
  }

  if (res.status === 401 && token) {
    const refreshed = await ensureRefresh();
    if (refreshed) {
      const newToken = localStorage.getItem('access_token');
      if (newToken) {
        headers.set('Authorization', `Bearer ${newToken}`);
        try {
          res = await fetch(input, { ...init, headers });
        } catch {
          return Response.error();
        }
      }
    }
  }

  return res;
}

export function scheduleRefresh(token: string) {
  if (refreshTimer) clearTimeout(refreshTimer);
  const exp = parseJwtExp(token);
  if (!exp) return;
  const msUntilRefresh = Math.max((exp - 60) * 1000 - Date.now(), 0);
  refreshTimer = setTimeout(async () => {
    const ok = await doRefresh();
    if (!ok) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
    }
  }, msUntilRefresh);
}

export function clearRefresh() {
  if (refreshTimer) clearTimeout(refreshTimer);
}
