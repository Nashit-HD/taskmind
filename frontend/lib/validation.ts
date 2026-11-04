// Form checks that mirror the API's Pydantic schemas, so a user hears about an empty or over-long
// field before a request is made. The API checks again; these limits are a copy, not the rule.

export const LIMITS = {
  noteTitle: 200,
  noteContent: 20_000,
  chatTitle: 100,
  message: 4000,
  passwordMin: 8,
  passwordMax: 128,
} as const;

/** The error for a field that must have text, after trimming, up to `max` characters. */
export function requiredText(value: string, max: number, label: string): string | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return `${label} is required`;
  }
  if (trimmed.length > max) {
    return `${label} must be at most ${max} characters`;
  }
  return null;
}

/** The error for a field that may be empty but has a ceiling. */
export function optionalText(value: string, max: number, label: string): string | null {
  if (value.length > max) {
    return `${label} must be at most ${max} characters`;
  }
  return null;
}

export function emailError(value: string): string | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return "Email is required";
  }
  // Something@something.something; the API does the real check.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
    return "Enter a valid email address";
  }
  return null;
}

export function passwordError(value: string, forRegister: boolean): string | null {
  if (value.length === 0) {
    return "Password is required";
  }
  if (forRegister && value.length < LIMITS.passwordMin) {
    return `Password must be at least ${LIMITS.passwordMin} characters`;
  }
  if (value.length > LIMITS.passwordMax) {
    return `Password must be at most ${LIMITS.passwordMax} characters`;
  }
  return null;
}
