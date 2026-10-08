import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import UserChip from "@/components/UserChip";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

let mockUser: { id: string; email: string } | null = null;
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ user: mockUser, isLoading: false }),
}));

describe("UserChip", () => {
  it("renders user email initial as avatar", () => {
    mockUser = { id: "1", email: "john@example.com" };
    render(<UserChip />);
    expect(screen.getByText("J")).toBeInTheDocument();
    expect(screen.getByText("john@example.com")).toBeInTheDocument();
  });

  it("renders 'U' initial when no email", () => {
    mockUser = null;
    render(<UserChip />);
    expect(screen.getByText("U")).toBeInTheDocument();
    expect(screen.getByText("User")).toBeInTheDocument();
  });

  it("links to /settings/profile", () => {
    mockUser = { id: "1", email: "test@test.com" };
    render(<UserChip />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/settings/profile");
  });
});
