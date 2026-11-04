// Shapes the API returns, as its OpenAPI schema declares them (backend/app/schemas). Timestamps
// are ISO 8601 strings in UTC.

export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: "bearer";
}

export interface Note {
  id: number;
  author_id: number;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface Chat {
  id: number;
  note_id: number;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export type Role = "user" | "assistant";

export interface Message {
  id: number;
  chat_id: number;
  role: Role;
  content: string;
  created_at: string;
}

export interface ChatDetail extends Chat {
  messages: Message[];
}

export interface MessageExchange {
  user_message: Message;
  assistant_message: Message;
}
