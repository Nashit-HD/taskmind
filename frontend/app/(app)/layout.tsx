import type { ReactNode } from "react";

import { Header } from "@/components/Header";
import { RequireAuth } from "@/components/RequireAuth";

// Every page in this group needs a signed-in user.
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <Header />
      <main className="main">{children}</main>
    </RequireAuth>
  );
}
