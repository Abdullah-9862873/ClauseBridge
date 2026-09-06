import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const mockReplace = vi.fn();
let mockPathname = "/";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => mockPathname,
}));

import AuthGuard from "@/components/AuthGuard";

describe("AuthGuard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  });

  it("renders children on public paths", () => {
    mockPathname = "/";
    render(
      <AuthGuard>
        <div>protected content</div>
      </AuthGuard>
    );
    expect(screen.getByText("protected content")).toBeInTheDocument();
  });

  it("renders children on /login", () => {
    mockPathname = "/login";
    render(
      <AuthGuard>
        <div>login content</div>
      </AuthGuard>
    );
    expect(screen.getByText("login content")).toBeInTheDocument();
  });

  it("redirects to /login when no token on protected path", () => {
    mockPathname = "/dashboard";
    render(
      <AuthGuard>
        <div>protected content</div>
      </AuthGuard>
    );
    expect(mockReplace).toHaveBeenCalledWith("/login");
  });

  it("renders children when token exists on protected path", () => {
    mockPathname = "/dashboard";
    localStorage.setItem("access_token", "valid-token");
    render(
      <AuthGuard>
        <div>protected content</div>
      </AuthGuard>
    );
    expect(screen.getByText("protected content")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
