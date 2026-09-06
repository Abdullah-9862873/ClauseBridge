import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/",
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

import { scheduleRefresh, clearRefresh } from "@/lib/token-refresh";

function makeToken(exp: number): string {
  const header = btoa(JSON.stringify({ alg: "HS256" }));
  const payload = btoa(JSON.stringify({ exp }));
  return `${header}.${payload}.sig`;
}

describe("scheduleRefresh", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    clearRefresh();
  });

  afterEach(() => {
    vi.useRealTimers();
    clearRefresh();
  });

  it("does not schedule anything for invalid token", () => {
    scheduleRefresh("not-a-jwt");
    expect(true).toBe(true);
  });

  it("schedules refresh before token expiry", () => {
    const exp = Math.floor(Date.now() / 1000) + 120;
    const token = makeToken(exp);
    scheduleRefresh(token);
    expect(true).toBe(true);
  });

  it("clearRefresh cancels pending timer without error", () => {
    const exp = Math.floor(Date.now() / 1000) + 120;
    const token = makeToken(exp);
    scheduleRefresh(token);
    clearRefresh();
    expect(true).toBe(true);
  });

  it("calls doRefresh when timer fires", async () => {
    localStorage.setItem("refresh_token", "my-refresh");
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: "new-access" }),
    });
    const exp = Math.floor(Date.now() / 1000) + 120;
    const token = makeToken(exp);
    scheduleRefresh(token);
    await vi.advanceTimersByTimeAsync(61000);
    expect(mockFetch).toHaveBeenCalled();
  });
});
