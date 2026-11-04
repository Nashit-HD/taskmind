"use client";

// The chats of one note, shared by the sidebar and the chat view so that a new message reorders
// the sidebar without a second fetch of the page.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, errorMessage } from "@/lib/api";
import type { Chat } from "@/lib/types";

export interface ChatsState {
  /** `null` until the first load answers. */
  chats: Chat[] | null;
  error: string | null;
  reload: () => Promise<void>;
  create: (title: string) => Promise<Chat>;
  rename: (id: number, title: string) => Promise<void>;
  remove: (id: number) => Promise<void>;
}

const ChatsContext = createContext<ChatsState | null>(null);

interface Loaded {
  noteId: number;
  chats: Chat[] | null;
  error: string | null;
}

export function useChats(): ChatsState {
  const state = useContext(ChatsContext);
  if (state === null) {
    throw new Error("useChats must be used inside ChatsProvider");
  }
  return state;
}

export function ChatsProvider({ noteId, children }: { noteId: number; children: ReactNode }) {
  // Keyed to the note id, so moving to another note shows loading, never the previous list.
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const chats = loaded?.noteId === noteId ? loaded.chats : null;
  const error = loaded?.noteId === noteId ? loaded.error : null;

  const load = useCallback(async (): Promise<Loaded> => {
    try {
      return { noteId, chats: await api.listChats(noteId), error: null };
    } catch (cause: unknown) {
      return { noteId, chats: null, error: errorMessage(cause) };
    }
  }, [noteId]);

  useEffect(() => {
    let cancelled = false;
    void load().then((result) => {
      if (!cancelled) {
        setLoaded(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const reload = useCallback(async () => {
    const result = await load();
    // On a failure the sidebar keeps its last list and shows why it could not refresh.
    setLoaded((current) =>
      result.error !== null && current?.noteId === noteId
        ? { ...current, error: result.error }
        : result,
    );
  }, [load, noteId]);

  const update = useCallback(
    (change: (chats: Chat[]) => Chat[]) => {
      setLoaded((current) =>
        current?.noteId === noteId && current.chats !== null
          ? { ...current, chats: change(current.chats) }
          : current,
      );
    },
    [noteId],
  );

  const create = useCallback(
    async (title: string) => {
      const chat = await api.createChat(noteId, title);
      update((current) => [chat, ...current]);
      return chat;
    },
    [noteId, update],
  );

  const rename = useCallback(
    async (id: number, title: string) => {
      const chat = await api.renameChat(id, title);
      update((current) => current.map((item) => (item.id === id ? chat : item)));
    },
    [update],
  );

  const remove = useCallback(
    async (id: number) => {
      await api.deleteChat(id);
      update((current) => current.filter((item) => item.id !== id));
    },
    [update],
  );

  const value = useMemo<ChatsState>(
    () => ({ chats, error, reload, create, rename, remove }),
    [chats, error, reload, create, rename, remove],
  );

  return <ChatsContext.Provider value={value}>{children}</ChatsContext.Provider>;
}
