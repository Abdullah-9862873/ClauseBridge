import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

const _store: Record<string, string> = {};

Object.defineProperty(window, "localStorage", {
  value: {
    getItem: (key: string) => _store[key] ?? null,
    setItem: (key: string, value: string) => { _store[key] = String(value); },
    removeItem: (key: string) => { delete _store[key]; },
    clear: () => { Object.keys(_store).forEach(k => delete _store[k]); },
    get length() { return Object.keys(_store).length; },
    key: (i: number) => Object.keys(_store)[i] ?? null,
  },
  writable: true,
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});
