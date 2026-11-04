"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useUser } from "@/components/RequireAuth";
import { clearToken } from "@/lib/session";

export function Header() {
  const user = useUser();
  const router = useRouter();

  function signOut() {
    clearToken();
    router.push("/sign-in");
  }

  return (
    <header className="header">
      <Link href="/notes" className="brand">
        TaskMind
      </Link>
      <nav aria-label="Main">
        <Link href="/notes">Notes</Link>
      </nav>
      <div className="header-user">
        <span>{user.email}</span>
        <button type="button" onClick={signOut}>
          Sign out
        </button>
      </div>
    </header>
  );
}
