// The bearer token lives in sessionStorage: it is gone when the tab closes, it is never sent by the
// browser on its own (so no cross-site request forgery handling is needed), and the API's CORS
// setup expects a bearer header, not a cookie. See docs/adr/0004-token-in-session-storage.md.

const TOKEN_KEY = "taskmind.token";

const listeners = new Set<() => void>();

function storage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    // Some privacy settings make the accessor itself throw. With no storage the user is simply
    // signed out, which RequireAuth turns into the sign-in page.
    return null;
  }
}

export function getToken(): string | null {
  return storage()?.getItem(TOKEN_KEY) ?? null;
}

export function setToken(token: string): void {
  storage()?.setItem(TOKEN_KEY, token);
  notify();
}

export function clearToken(): void {
  storage()?.removeItem(TOKEN_KEY);
  notify();
}

/** Subscribe to token changes made through this module. Shaped for `useSyncExternalStore`. */
export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notify(): void {
  for (const listener of listeners) {
    listener();
  }
}
