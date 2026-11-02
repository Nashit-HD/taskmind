"use client";

// Wraps every signed-in page: no token means the sign-in page, a token means the user is loaded
// from /auth/me and handed down through `useUser`. The API still checks every request itself;
// this only decides what to render.

import { useRouter } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { ErrorMessage, Loading } from "@/components/Status";
import { api, errorMessage } from "@/lib/api";
import { getToken, subscribe } from "@/lib/session";
import type { User } from "@/lib/types";

const UserContext = createContext<User | null>(null);

interface Loaded {
  token: string;
  user: User | null;
  error: string | null;
}

export function useUser(): User {
  const user = useContext(UserContext);
  if (user === null) {
    throw new Error("useUser must be used inside RequireAuth");
  }
  return user;
}

// The server has no sessionStorage, so it renders the loading state and the browser takes over.
function serverToken(): null {
  return null;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const token = useSyncExternalStore(subscribe, getToken, serverToken);
  // Keyed to the token they came from, so a new token never shows the previous user or error.
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const user = loaded?.token === token ? loaded.user : null;
  const error = loaded?.token === token ? loaded.error : null;

  useEffect(() => {
    if (token === null) {
      router.replace("/sign-in");
      return;
    }
    let cancelled = false;
    api
      .me()
      .then((me) => {
        if (!cancelled) {
          setLoaded({ token, user: me, error: null });
        }
      })
      .catch((cause: unknown) => {
        // A 401 has already cleared the token, which re-runs this effect and redirects. Anything
        // else (the API down) is shown; there is nothing to retry automatically.
        if (!cancelled) {
          setLoaded({ token, user: null, error: errorMessage(cause) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, router]);

  if (token === null) {
    return <Loading label="Checking your session" />;
  }
  if (error !== null) {
    return <ErrorMessage message={error} />;
  }
  if (user === null) {
    return <Loading label="Loading your account" />;
  }
  return <UserContext.Provider value={user}>{children}</UserContext.Provider>;
}
