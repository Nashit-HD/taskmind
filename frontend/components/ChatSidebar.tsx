"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { ErrorMessage, Loading } from "@/components/Status";
import { useChats } from "@/app/(app)/notes/[noteId]/chats/ChatsProvider";
import { errorMessage } from "@/lib/api";
import type { Chat } from "@/lib/types";
import { LIMITS, requiredText } from "@/lib/validation";

export function ChatSidebar({ noteId }: { noteId: number }) {
  const { chats, error, create, rename, remove } = useChats();
  const params = useParams<{ chatId?: string }>();
  const router = useRouter();
  const activeId = params.chatId === undefined ? null : Number(params.chatId);

  async function handleCreate(title: string) {
    const chat = await create(title);
    router.push(`/notes/${noteId}/chats/${chat.id}`);
  }

  async function handleDelete(chat: Chat) {
    await remove(chat.id);
    if (chat.id === activeId) {
      router.push(`/notes/${noteId}/chats`);
    }
  }

  return (
    <div className="sidebar">
      <h2>Chats</h2>
      <TitleForm label="New chat" submitLabel="Start chat" onSubmit={handleCreate} />
      {error !== null && <ErrorMessage message={error} />}
      {error === null && chats === null && <Loading label="Loading chats" />}
      {chats !== null && chats.length === 0 && <p className="empty">No chats on this note yet.</p>}
      {chats !== null && chats.length > 0 && (
        <ul className="chat-list">
          {chats.map((chat) => (
            <li key={chat.id}>
              <ChatRow
                chat={chat}
                noteId={noteId}
                active={chat.id === activeId}
                onRename={(title) => rename(chat.id, title)}
                onDelete={() => handleDelete(chat)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface ChatRowProps {
  chat: Chat;
  noteId: number;
  active: boolean;
  onRename: (title: string) => Promise<void>;
  onDelete: () => Promise<void>;
}

function ChatRow({ chat, noteId, active, onRename, onDelete }: ChatRowProps) {
  const [renaming, setRenaming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    if (!window.confirm(`Delete the chat "${chat.title}" and its messages?`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onDelete();
    } catch (cause: unknown) {
      setError(errorMessage(cause));
      setBusy(false);
    }
  }

  if (renaming) {
    return (
      <TitleForm
        label="New title"
        submitLabel="Save"
        initial={chat.title}
        onSubmit={async (title) => {
          await onRename(title);
          setRenaming(false);
        }}
        onCancel={() => setRenaming(false)}
      />
    );
  }

  return (
    <div className={active ? "chat-row active" : "chat-row"}>
      <Link href={`/notes/${noteId}/chats/${chat.id}`} aria-current={active ? "page" : undefined}>
        {chat.title}
      </Link>
      {error !== null && <ErrorMessage message={error} />}
      <div className="actions">
        <button
          type="button"
          className="secondary"
          onClick={() => setRenaming(true)}
          disabled={busy}
        >
          Rename
        </button>
        <button type="button" className="danger" onClick={handleDelete} disabled={busy}>
          Delete
        </button>
      </div>
    </div>
  );
}

interface TitleFormProps {
  label: string;
  submitLabel: string;
  initial?: string;
  onSubmit: (title: string) => Promise<void>;
  onCancel?: () => void;
}

/** A one-field form for a chat title; used to start a chat and to rename one. */
function TitleForm({ label, submitLabel, initial, onSubmit, onCancel }: TitleFormProps) {
  const id = useId();
  const [title, setTitle] = useState(initial ?? "");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const error = requiredText(title, LIMITS.chatTitle, "Title");
    setFieldError(error);
    setSubmitError(null);
    if (error !== null) {
      return;
    }
    setPending(true);
    try {
      await onSubmit(title.trim());
      if (initial === undefined) {
        setTitle("");
      }
    } catch (cause: unknown) {
      setSubmitError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="form inline" aria-busy={pending}>
      <div className="field">
        <label htmlFor={id}>{label}</label>
        <input
          id={id}
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          aria-invalid={fieldError !== null}
          aria-describedby={fieldError !== null ? `${id}-error` : undefined}
        />
        {fieldError !== null && (
          <p id={`${id}-error`} className="field-error">
            {fieldError}
          </p>
        )}
      </div>
      {submitError !== null && <ErrorMessage message={submitError} />}
      <div className="actions">
        <button type="submit" disabled={pending}>
          {submitLabel}
        </button>
        {onCancel !== undefined && (
          <button type="button" className="secondary" onClick={onCancel} disabled={pending}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
