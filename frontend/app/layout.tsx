import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "TaskMind",
  description: "Shared notes, each with a private chat to an assistant that answers from the note.",
};

// System fonts only: nothing to download before text can show.
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
