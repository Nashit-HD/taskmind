import { formatDateTime } from "@/lib/format";
import type { Message } from "@/lib/types";

export function MessageList({ messages }: { messages: Message[] }) {
  if (messages.length === 0) {
    return <p className="empty">No messages yet. Ask something about the note.</p>;
  }
  return (
    <ol className="messages" aria-label="Messages">
      {messages.map((message) => (
        <li key={message.id} className={`message message-${message.role}`}>
          <span className="message-role">{message.role === "user" ? "You" : "Assistant"}</span>
          <p>{message.content}</p>
          <time dateTime={message.created_at} className="meta">
            {formatDateTime(message.created_at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
