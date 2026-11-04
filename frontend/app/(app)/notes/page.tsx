"use client";

import { useEffect, useState } from "react";

import { NoteForm, type NoteValues } from "@/components/NoteForm";
import { NoteItem } from "@/components/NoteItem";
import { useUser } from "@/components/RequireAuth";
import { ErrorMessage, Loading } from "@/components/Status";
import { api, errorMessage } from "@/lib/api";
import type { Note } from "@/lib/types";

export default function NotesPage() {
  const user = useUser();
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listNotes()
      .then((loaded) => {
        if (!cancelled) {
          setNotes(loaded);
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
  }, []);

  async function create(values: NoteValues) {
    const note = await api.createNote(values.title, values.content);
    setNotes((current) => [note, ...(current ?? [])]);
  }

  async function update(id: number, values: NoteValues) {
    const note = await api.updateNote(id, values.title, values.content);
    setNotes((current) => current?.map((item) => (item.id === id ? note : item)) ?? null);
  }

  async function remove(id: number) {
    await api.deleteNote(id);
    setNotes((current) => current?.filter((item) => item.id !== id) ?? null);
  }

  return (
    <>
      <h1>Notes</h1>
      <section aria-labelledby="new-note">
        <h2 id="new-note">New note</h2>
        <NoteForm submitLabel="Create note" onSubmit={create} />
      </section>
      <section aria-labelledby="all-notes">
        <h2 id="all-notes">All notes</h2>
        {error !== null && <ErrorMessage message={error} />}
        {error === null && notes === null && <Loading label="Loading notes" />}
        {notes !== null && notes.length === 0 && <p className="empty">No notes yet.</p>}
        {notes !== null && notes.length > 0 && (
          <ul className="note-list">
            {notes.map((note) => (
              <li key={note.id}>
                <NoteItem
                  note={note}
                  canEdit={note.author_id === user.id}
                  onUpdate={update}
                  onDelete={remove}
                />
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
