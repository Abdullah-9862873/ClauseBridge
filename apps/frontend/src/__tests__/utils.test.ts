import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("cn", () => {
  it("returns a single class name", () => {
    expect(cn("foo")).toBe("foo");
  });

  it("merges multiple class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("foo", false && "bar", "baz")).toBe("foo baz");
  });

  it("resolves tailwind conflicts", () => {
    expect(cn("px-4", "px-8")).toBe("px-8");
  });

  it("returns empty string for no args", () => {
    expect(cn()).toBe("");
  });
});
