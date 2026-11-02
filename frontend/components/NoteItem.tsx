"use client";

import Link from "next/link";
import { useState } from "react";

import { NoteForm, type NoteValues } from "@/components/NoteForm";
import { ErrorMessage } from "@/components/Status";
import { errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Note } from "@/lib/types";

interface NoteItemProps {
  note: Note;
  /** Only the author edits or deletes. The API refuses anyone else; this hides the buttons. */
  canEdit: boolean;
  onUpdate: (id: number, values: NoteValues) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}

export function NoteItem({ note, canEdit, onUpdate, onDelete }: NoteItemProps) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete() {
    if (!window.confirm(`Delete "${note.title}"? Its chats are deleted with it.`)) {
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      await onDelete(note.id);
    } catch (cause: unknown) {
      setDeleteError(errorMessage(cause));
      setDeleting(false);
    }
  }

  if (editing) {
    return (
      <article className="note">
        <h3>Edit note</h3>
        <NoteForm
          initial={{ title: note.title, content: note.content }}
          submitLabel="Save"
          onSubmit={async (values) => {
            await onUpdate(note.id, values);
            setEditing(false);
          }}
          onCancel={() => setEditing(false)}
        />
      </article>
    );
  }

  return (
    <article className="note" aria-labelledby={`note-${note.id}-title`}>
      <h3 id={`note-${note.id}-title`}>{note.title}</h3>
      <p className="meta">
        Updated <time dateTime={note.updated_at}>{formatDateTime(note.updated_at)}</time>
      </p>
      {note.content.length > 0 && <p className="note-content">{note.content}</p>}
      {deleteError !== null && <ErrorMessage message={deleteError} />}
      <div className="actions">
        <Link href={`/notes/${note.id}/chats`} className="button-link">
          Chats
        </Link>
        {canEdit && (
          <>
            <button type="button" className="secondary" onClick={() => setEditing(true)}>
              Edit
            </button>
            <button type="button" className="danger" onClick={handleDelete} disabled={deleting}>
              Delete
            </button>
          </>
        )}
      </div>
    </article>
  );
}
