"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ChatsProvider } from "@/app/(app)/notes/[noteId]/chats/ChatsProvider";
import { ChatSidebar } from "@/components/ChatSidebar";
import { ErrorMessage, Loading } from "@/components/Status";
import { api, errorMessage } from "@/lib/api";
import type { Note } from "@/lib/types";

/** The note's id from the URL, or `null` when the segment is not a positive integer. */
export function parseId(segment: string | undefined): number | null {
  const id = Number(segment);
  return Number.isInteger(id) && id > 0 ? id : null;
}

export default function NoteChatsLayout({ children }: { children: ReactNode }) {
  const params = useParams<{ noteId: string }>();
  const noteId = parseId(params.noteId);
  const [note, setNote] = useState<Note | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (noteId === null) {
      return;
    }
    let cancelled = false;
    api
      .getNote(noteId)
      .then((loaded) => {
        if (!cancelled) {
          setNote(loaded);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(errorMessage(cause));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [noteId]);

  if (noteId === null) {
    return <ErrorMessage message="Note not found" />;
  }
  if (error !== null) {
    return <ErrorMessage message={error} />;
  }
  if (note === null) {
    return <Loading label="Loading note" />;
  }
  return (
    <ChatsProvider noteId={noteId}>
      <nav aria-label="Breadcrumb" className="breadcrumb">
        <Link href="/notes">Notes</Link> / <span>{note.title}</span>
      </nav>
      <h1>{note.title}</h1>
      <div className="chats-layout">
        <aside>
          <ChatSidebar noteId={noteId} />
        </aside>
        <section className="chat-main">{children}</section>
      </div>
    </ChatsProvider>
  );
}
