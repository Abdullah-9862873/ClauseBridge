import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { type ReactNode } from "react";
import { ToastProvider, useToast } from "@/lib/toast-context";

function wrapper({ children }: { children: ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}

describe("ToastProvider", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts with empty toasts", () => {
    const { result } = renderHook(() => useToast(), { wrapper });
    expect(result.current.toasts).toEqual([]);
  });

  it("showToast adds a toast with an id", () => {
    const { result } = renderHook(() => useToast(), { wrapper });
    act(() => {
      result.current.showToast({ message: "hello", type: "success" });
    });
    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].message).toBe("hello");
    expect(result.current.toasts[0].type).toBe("success");
    expect(result.current.toasts[0].id).toBeDefined();
  });

  it("removeToast removes a toast by id", () => {
    const { result } = renderHook(() => useToast(), { wrapper });
    act(() => {
      result.current.showToast({ message: "hello", type: "success" });
    });
    const toastId = result.current.toasts[0].id;
    act(() => {
      result.current.removeToast(toastId);
    });
    expect(result.current.toasts).toHaveLength(0);
  });

  it("auto-removes toast after 6 seconds", () => {
    const { result } = renderHook(() => useToast(), { wrapper });
    act(() => {
      result.current.showToast({ message: "gone soon", type: "error" });
    });
    expect(result.current.toasts).toHaveLength(1);
    act(() => {
      vi.advanceTimersByTime(6000);
    });
    expect(result.current.toasts).toHaveLength(0);
  });

  it("throws when used outside provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useToast())).toThrow(
      "useToast must be used within ToastProvider"
    );
    spy.mockRestore();
  });
});
