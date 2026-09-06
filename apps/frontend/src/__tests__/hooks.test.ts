import { describe, it, expect, beforeEach } from "vitest";
import { getPdfUrl, getReportUrl } from "@/lib/hooks";

describe("getPdfUrl", () => {
  beforeEach(() => {
    localStorage.removeItem("access_token");
  });

  it("returns URL with token", () => {
    localStorage.setItem("access_token", "my-token");
    const url = getPdfUrl("case-1", "doc-1");
    expect(url).toBe(
      "http://localhost:8000/api/v1/cases/case-1/documents/doc-1/pdf?token=my-token"
    );
  });

  it("returns URL with null token when no token stored", () => {
    const url = getPdfUrl("case-1", "doc-1");
    expect(url).toContain("token=null");
  });
});

describe("getReportUrl", () => {
  beforeEach(() => {
    localStorage.removeItem("access_token");
  });

  it("returns URL with token", () => {
    localStorage.setItem("access_token", "report-token");
    const url = getReportUrl("case-42");
    expect(url).toBe(
      "http://localhost:8000/api/v1/cases/case-42/report/pdf?token=report-token"
    );
  });

  it("returns URL with null token when no token stored", () => {
    const url = getReportUrl("case-42");
    expect(url).toContain("token=null");
  });
});
