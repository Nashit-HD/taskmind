// The one place the app talks to the API. Every call goes through `request`, which adds the bearer
// token, bounds the wait, and turns a failed response into an `ApiError` the UI can show.

import { API_URL } from "@/lib/config";
import { clearToken, getToken } from "@/lib/session";
import type { Chat, ChatDetail, MessageExchange, Note, Token, User } from "@/lib/types";

export const REQUEST_TIMEOUT_MS = 10_000;
// Posting a message waits on the assistant: the API allows OpenAI 30 s per attempt, 3 attempts.
export const MESSAGE_TIMEOUT_MS = 100_000;

/** The API answered with an error status. `message` is its `detail`, fit to show the user. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** The API did not answer: the network failed or the wait ran out. */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

interface RequestOptions {
  body?: unknown;
  timeoutMs?: number;
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const token = getToken();
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: AbortSignal.timeout(options.timeoutMs ?? REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    // fetch rejects when the network fails or the timeout signal fires. Neither carries an answer,
    // so both become a NetworkError the form shows; nothing is retried, the user resends.
    const timedOut = error instanceof DOMException && error.name === "TimeoutError";
    throw new NetworkError(
      timedOut ? "The server took too long to answer" : "Could not reach the server",
    );
  }

  if (!response.ok) {
    if (response.status === 401) {
      // The token is expired or bad; dropping it sends the user back to sign in.
      clearToken();
    }
    throw new ApiError(response.status, await detailOf(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  // The API's OpenAPI schema is the contract for the shape; see lib/types.ts.
  return (await response.json()) as T;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** The API's `{"detail": ...}`: a string, or Pydantic's list of `{msg}` items on a 422. */
async function detailOf(response: Response): Promise<string> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return fallbackMessage(response.status);
  }
  if (isRecord(body)) {
    const detail = body.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item: unknown) => (isRecord(item) && typeof item.msg === "string" ? item.msg : null))
        .filter((message): message is string => message !== null);
      if (messages.length > 0) {
        return messages.join("; ");
      }
    }
  }
  return fallbackMessage(response.status);
}

function fallbackMessage(status: number): string {
  return status >= 500 ? "The server had a problem" : `Request failed (${status})`;
}

export const api = {
  register: (email: string, password: string) =>
    request<User>("POST", "/auth/register", { body: { email, password } }),
  login: (email: string, password: string) =>
    request<Token>("POST", "/auth/login", { body: { email, password } }),
  me: () => request<User>("GET", "/auth/me"),

  // The API returns the newest 50 by default. Paging is not built; see the README.
  listNotes: () => request<Note[]>("GET", "/notes"),
  getNote: (id: number) => request<Note>("GET", `/notes/${id}`),
  createNote: (title: string, content: string) =>
    request<Note>("POST", "/notes", { body: { title, content } }),
  updateNote: (id: number, title: string, content: string) =>
    request<Note>("PUT", `/notes/${id}`, { body: { title, content } }),
  deleteNote: (id: number) => request<void>("DELETE", `/notes/${id}`),

  listChats: (noteId: number) => request<Chat[]>("GET", `/notes/${noteId}/chats`),
  createChat: (noteId: number, title: string) =>
    request<Chat>("POST", `/notes/${noteId}/chats`, { body: { title } }),
  getChat: (id: number) => request<ChatDetail>("GET", `/chats/${id}`),
  renameChat: (id: number, title: string) =>
    request<Chat>("PUT", `/chats/${id}`, { body: { title } }),
  deleteChat: (id: number) => request<void>("DELETE", `/chats/${id}`),
  postMessage: (chatId: number, content: string) =>
    request<MessageExchange>("POST", `/chats/${chatId}/messages`, {
      body: { content },
      timeoutMs: MESSAGE_TIMEOUT_MS,
    }),
};

/** What to show the user for a failure from `api`. Anything unexpected gets a generic line. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  return "Something went wrong";
}
