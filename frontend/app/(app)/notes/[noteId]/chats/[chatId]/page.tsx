"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { parseId } from "@/app/(app)/notes/[noteId]/chats/layout";
import { useChats } from "@/app/(app)/notes/[noteId]/chats/ChatsProvider";
import { MessageComposer } from "@/components/MessageComposer";
import { MessageList } from "@/components/MessageList";
import { ErrorMessage, Loading } from "@/components/Status";
import { api, errorMessage } from "@/lib/api";
import type { ChatDetail } from "@/lib/types";

interface Loaded {
  id: number;
  chat: ChatDetail | null;
  error: string | null;
}

export default function ChatPage() {
  const params = useParams<{ chatId: string }>();
  const chatId = parseId(params.chatId);
  const { chats, reload } = useChats();
  // Keyed to the chat id, so switching chats shows the loading state, never the previous chat.
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const chat = loaded?.id === chatId ? loaded.chat : null;
  const error = loaded?.id === chatId ? loaded.error : null;

  useEffect(() => {
    if (chatId === null) {
      return;
    }
    let cancelled = false;
    api
      .getChat(chatId)
      .then((detail) => {
        if (!cancelled) {
          setLoaded({ id: chatId, chat: detail, error: null });
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setLoaded({ id: chatId, chat: null, error: errorMessage(cause) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [chatId]);

  // A rename in the sidebar shows here without refetching the messages.
  const title = chats?.find((item) => item.id === chatId)?.title ?? chat?.title;

  async function send(content: string) {
    if (chatId === null) {
      return;
    }
    const exchange = await api.postMessage(chatId, content);
    setLoaded((current) =>
      current === null || current.chat === null || current.id !== chatId
        ? current
        : {
            ...current,
            chat: {
              ...current.chat,
              messages: [
                ...current.chat.messages,
                exchange.user_message,
                exchange.assistant_message,
              ],
            },
          },
    );
    // The API bumped the chat's updated_at; the sidebar re-sorts.
    await reload();
  }

  if (chatId === null) {
    return <ErrorMessage message="Chat not found" />;
  }
  if (error !== null) {
    return <ErrorMessage message={error} />;
  }
  if (chat === null) {
    return <Loading label="Loading chat" />;
  }
  return (
    <>
      <h2>{title}</h2>
      <MessageList messages={chat.messages} />
      <MessageComposer onSend={send} />
    </>
  );
}
