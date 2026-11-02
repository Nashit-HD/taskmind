import { emailError, optionalText, passwordError, requiredText } from "@/lib/validation";

describe("requiredText", () => {
  it("rejects empty and whitespace-only text", () => {
    expect(requiredText("", 10, "Title")).toBe("Title is required");
    expect(requiredText("   ", 10, "Title")).toBe("Title is required");
  });

  it("accepts text up to the limit after trimming", () => {
    expect(requiredText("a", 10, "Title")).toBeNull();
    expect(requiredText(`  ${"x".repeat(10)}  `, 10, "Title")).toBeNull();
  });

  it("rejects text one past the limit", () => {
    expect(requiredText("x".repeat(11), 10, "Title")).toBe("Title must be at most 10 characters");
  });
});

describe("optionalText", () => {
  it("accepts empty text and text at the limit", () => {
    expect(optionalText("", 5, "Content")).toBeNull();
    expect(optionalText("abcde", 5, "Content")).toBeNull();
  });

  it("rejects text past the limit", () => {
    expect(optionalText("abcdef", 5, "Content")).toBe("Content must be at most 5 characters");
  });
});

describe("emailError", () => {
  it("requires an address with a domain", () => {
    expect(emailError("")).toBe("Email is required");
    expect(emailError("ada")).toBe("Enter a valid email address");
    expect(emailError("ada@example")).toBe("Enter a valid email address");
    expect(emailError(" ada@example.com ")).toBeNull();
  });
});

describe("passwordError", () => {
  it("requires a password", () => {
    expect(passwordError("", false)).toBe("Password is required");
  });

  it("applies the minimum only when registering", () => {
    expect(passwordError("short", false)).toBeNull();
    expect(passwordError("short", true)).toBe("Password must be at least 8 characters");
    expect(passwordError("12345678", true)).toBeNull();
  });

  it("rejects a password past the maximum", () => {
    expect(passwordError("x".repeat(129), false)).toBe("Password must be at most 128 characters");
  });
});
