"use client";

import { useId, useState, type FormEvent } from "react";

import { ErrorMessage } from "@/components/Status";
import { errorMessage } from "@/lib/api";
import { LIMITS, optionalText, requiredText } from "@/lib/validation";

export interface NoteValues {
  title: string;
  content: string;
}

interface NoteFormProps {
  /** Editing an existing note: the form starts filled and keeps its values after saving. */
  initial?: NoteValues;
  submitLabel: string;
  onSubmit: (values: NoteValues) => Promise<void>;
  onCancel?: () => void;
}

interface FieldErrors {
  title?: string;
  content?: string;
}

export function NoteForm({ initial, submitLabel, onSubmit, onCancel }: NoteFormProps) {
  const ids = { title: useId(), content: useId() };
  const [title, setTitle] = useState(initial?.title ?? "");
  const [content, setContent] = useState(initial?.content ?? "");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: FieldErrors = {
      title: requiredText(title, LIMITS.noteTitle, "Title") ?? undefined,
      content: optionalText(content, LIMITS.noteContent, "Content") ?? undefined,
    };
    setFieldErrors(errors);
    setSubmitError(null);
    if (errors.title !== undefined || errors.content !== undefined) {
      return;
    }
    setPending(true);
    try {
      await onSubmit({ title: title.trim(), content });
      if (initial === undefined) {
        setTitle("");
        setContent("");
      }
    } catch (cause: unknown) {
      setSubmitError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="form" aria-busy={pending}>
      <div className="field">
        <label htmlFor={ids.title}>Title</label>
        <input
          id={ids.title}
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          aria-invalid={fieldErrors.title !== undefined}
          aria-describedby={fieldErrors.title !== undefined ? `${ids.title}-error` : undefined}
        />
        {fieldErrors.title !== undefined && (
          <p id={`${ids.title}-error`} className="field-error">
            {fieldErrors.title}
          </p>
        )}
      </div>
      <div className="field">
        <label htmlFor={ids.content}>Content</label>
        <textarea
          id={ids.content}
          rows={6}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          aria-invalid={fieldErrors.content !== undefined}
          aria-describedby={fieldErrors.content !== undefined ? `${ids.content}-error` : undefined}
        />
        {fieldErrors.content !== undefined && (
          <p id={`${ids.content}-error`} className="field-error">
            {fieldErrors.content}
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
