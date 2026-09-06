import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ToastContainer from "@/components/Toast";

const mockRemoveToast = vi.fn();
let mockToasts: any[] = [];

vi.mock("@/lib/toast-context", () => ({
  useToast: () => ({
    toasts: mockToasts,
    removeToast: mockRemoveToast,
  }),
}));

describe("ToastContainer", () => {
  it("renders nothing when no toasts", () => {
    mockToasts = [];
    const { container } = render(<ToastContainer />);
    expect(container.firstChild).toBeNull();
  });

  it("renders toast messages", () => {
    mockToasts = [
      { id: "1", message: "Success!", type: "success" },
      { id: "2", message: "Error occurred", type: "error" },
    ];
    render(<ToastContainer />);
    expect(screen.getByText("Success!")).toBeInTheDocument();
    expect(screen.getByText("Error occurred")).toBeInTheDocument();
  });

  it("calls removeToast when close button clicked", () => {
    mockToasts = [{ id: "abc", message: "test", type: "success" }];
    render(<ToastContainer />);
    fireEvent.click(screen.getByLabelText("Close"));
    expect(mockRemoveToast).toHaveBeenCalledWith("abc");
  });

  it("renders retry button when onRetry provided", () => {
    const onRetry = vi.fn();
    mockToasts = [{ id: "1", message: "retry msg", type: "error", onRetry }];
    render(<ToastContainer />);
    const retryBtn = screen.getByText("Retry");
    expect(retryBtn).toBeInTheDocument();
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalled();
    expect(mockRemoveToast).toHaveBeenCalledWith("1");
  });
});
