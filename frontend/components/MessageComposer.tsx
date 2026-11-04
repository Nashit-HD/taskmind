"use client";

import { useId, useState, type FormEvent } from "react";

import { ErrorMessage } from "@/components/Status";
import { errorMessage } from "@/lib/api";
import { LIMITS, requiredText } from "@/lib/validation";

interface MessageComposerProps {
  onSend: (content: string) => Promise<void>;
}

export function MessageComposer({ onSend }: MessageComposerProps) {
  const id = useId();
  const [content, setContent] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const error = requiredText(content, LIMITS.message, "Message");
    setFieldError(error);
    setSubmitError(null);
    if (error !== null) {
      return;
    }
    setSending(true);
    try {
      await onSend(content.trim());
      setContent("");
    } catch (cause: unknown) {
      // The text stays in the box so the user can send it again.
      setSubmitError(errorMessage(cause));
    } finally {
      setSending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="composer" aria-busy={sending}>
      <div className="field">
        <label htmlFor={id}>Message</label>
        <textarea
          id={id}
          rows={3}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          disabled={sending}
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
        <button type="submit" disabled={sending}>
          {sending ? "Waiting for the assistant…" : "Send"}
        </button>
      </div>
    </form>
  );
}
