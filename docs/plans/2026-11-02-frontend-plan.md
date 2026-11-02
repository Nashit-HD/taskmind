# Frontend Implementation Plan

> **For agentic workers:** Use `/explain-plan` to preview all tasks, then `/execute-plan` to implement task-by-task.

**Goal:** Give TaskMind its Next.js frontend: sign-in, the notes page, a chats sidebar and chat view per note, loading, error and validation states, its own Dockerfile, all three services under Compose, and the README's "next steps" written at the deadline.

**Spec:** the assignment's § Frontend requirements and § Deliverables (`TaskMind To-Do App — Project Plan.md`, outside the repo), read with the backend design `docs/plans/2026-10-20-backend-design.md` (bearer tokens from the browser, CORS for `http://localhost:3000`, note-scoped private chats per ADR 0003). Terms per `GLOSSARY.md`.

**Affected components:** frontend — `frontend/`; `docker-compose.yml`, `.env.example`, `.gitignore`, `.github/workflows/ci.yml`, `README.md`, `AGENTS.md` and `docs/adr/` at the repo root

**Change class:** structural — a new component with its own toolchain, test setup, Dockerfile and CI job; the first frontend change, so what it does becomes the pattern (`maintainability.md` rule 11). Elevated per `review.md` § Overrides: it handles the sign-in token.

| Revision | Closed | Sections changed |
|---|---|---|
| r2 | B1, N1, N2 | Task 3 (gate tests), Task 2 and Task 4 check counts, Task 6 (`AGENTS.md` Key Commands) |

**Branch:** `feat/frontend`, cut from `feat/chats`, which now carries PRs 5 to 7 (chats, Docker backend, OpenAI assistant) after #7 and #8 were merged into it. The pages need the chats API and the Compose backend service, so the PR targets `feat/chats`; GitHub retargets it to `main` when #6 merges.

---

## Policy answers, checked

- **Entry points and authorisation.** The frontend adds no data entry point: every read and write
  is a browser call to the API, which checks the token and the actor on every request
  (`security.md` rules 1 to 3 are met there, unchanged). `components/RequireAuth.tsx` wraps the
  `app/(app)` route group: no token renders nothing and goes to `/sign-in`; a token loads
  `/auth/me` and provides the user. The notes page hides Edit and Delete unless the note's
  `author_id` is the user's id; that is presentation, the API still answers 403 to anyone else.
  The Next.js server itself serves only static pages and `/health`.
- **The token.** Kept in `sessionStorage` and sent as `Authorization: Bearer`, as the backend
  design decided; ADR 0004 records the alternatives (httpOnly cookie with a proxy; `localStorage`)
  and the cost accepted. No cookie carries the token, so the browser never attaches it by itself
  and `security.md` rule 25 (request forgery) does not apply; the API's CORS stays
  `allow_credentials=False`. Sign-out and any 401 clear it (`lib/session.ts`). The hour-long
  expiry is enforced by the API (`security.md` rule 29).
- **Input.** `lib/validation.ts` copies the API's limits (title 200, chat title 100, content
  20 000, message 4000, password 8 to 128) so a user hears about an empty or over-long field before
  a request. The API is the rule (`security.md` rules 7 and 13); a 422 it returns is shown as its
  `msg` text.
- **Output.** Text renders through React, which encodes it; nothing uses
  `dangerouslySetInnerHTML` (`security.md` rule 9).
- **Outbound calls.** All in `lib/api.ts`. Every `fetch` carries `AbortSignal.timeout`: 10 s, and
  100 s for posting a message, because the API gives OpenAI 30 s per attempt and up to 3 attempts
  (`reliability.md` rules 5 and 17). No automatic retry: a message post is not idempotent and the
  user can resend; the text stays in the box (`reliability.md` rule 6). A failing API degrades to
  an error line in the form or page that made the call, never a blank page (`reliability.md`
  rule 7). Failures are told apart by status code and error class, never message text
  (`reliability.md` rule 4).
- **Error paths and what the app emits.** Every `catch` sets state that renders as
  `role="alert"` with the API's `detail` or a fixed line; that is the emission a browser app has
  (`observability.md` rule 3). The lint config forbids `console` so nothing leaks to the
  devtools by accident. Server side, Next.js logs each request to stdout
  (`docker compose logs frontend`), and every API call is already logged by the API with its
  request id. The three lines `observability.md` rule 9 asks for go in the PR.
- **Data volumes.** The notes page shows the API's first page (50 newest); the sidebar the 50 most
  recently updated chats; a chat its most recent 200 messages. All bounded by the API
  (`performance.md` rule 1); paging in the UI is recorded as a next step. No loop makes a request.
- **What could slow a page** (`performance.md` rule 15). Two sequential calls before the notes
  page shows, `/auth/me` then `/notes`; the fix offered is caching the user beside the token, not
  taken for a prototype. Nothing else seen: system fonts, no images, no third-party script, no
  content that moves as it loads (every list has a loading line in its place). No bundle ceiling
  is declared yet (`performance.md` rule 16); recorded under gaps.
- **Dependencies** (`security.md` rule 24). Runtime: `next`, `react`, `react-dom`. Development:
  TypeScript, ESLint with `eslint-config-next`, Prettier, Vitest with `@vitejs/plugin-react`,
  `jsdom`, Testing Library (`react`, `jest-dom`, `user-event`) and `@vitest/coverage-v8`. No UI
  kit, no fetch wrapper, no state library: plain CSS and `fetch` cover a prototype of this size.
- **Testing.** Vitest in jsdom. Unit tests for validation (empty, whitespace, the limit, one past
  it), the session store, and the API client with `fetch` stubbed at the process boundary
  (`testing.md` rule 10): JSON in and out, bearer header, 204, `detail` string and list, 401
  clearing the token, network failure, timeout, the longer message timeout. Component tests for
  the three forms: blocked when empty or over-long, submitted trimmed, and the failure path shown;
  and for the gate: no token or a rejected token goes to sign in with nothing rendered, a good
  token renders the page, an unreachable API shows the failure.
  Changed-line coverage through `diff-cover` at the prototype figure of 20%
  (`testing.md` rule 14), with Vitest's Cobertura report. No end-to-end test: recorded as a gap.
- **Build, config, pipeline.** `frontend/Dockerfile` pins `node:24-alpine` by digest, installs
  from `package-lock.json` with `npm ci` in a cached layer, builds with `output: "standalone"`,
  and runs as the image's `node` user (`devops.md` rules 2, 3, 19). `.node-version` pins the
  runtime; `setup-node` reads it in CI and is pinned by commit (`devops.md` rule 15). The
  Validate command gains `npm run validate` (lint, format, `tsc`, tests), so the type checker is
  inside it (`devops.md` rule 20). `.env.example` names `FRONTEND_PORT` and `NEXT_PUBLIC_API_URL`
  (`devops.md` rule 4). The `compose` job now waits for all three services and curls both
  `/health` endpoints.
- **Cloud, monitoring, alerts.** Not applicable: nothing is deployed.

### Departures from the assignment, stated

- **Chats live under their note.** The assignment names `/chats` and `/chats/[id]`. In this
  design a chat belongs to one note (ADR 0003) and the API lists chats per note, so the chats
  page is `/notes/{id}/chats` and the chat view `/notes/{id}/chats/{chatId}`. A cross-note list
  would need a new API endpoint; not built.
- **Search by title, paging in the UI and frontend end-to-end tests** are not built; the README's
  next steps say so.

## Files

| File | Job |
|---|---|
| `frontend/package.json`, `package-lock.json`, `.node-version` | Dependencies pinned by the lockfile, the scripts, the runtime pin |
| `frontend/tsconfig.json`, `next.config.ts`, `eslint.config.mjs`, `.prettierrc`, `.prettierignore` | Strict TypeScript, standalone output, lint and format |
| `frontend/vitest.config.ts`, `vitest.setup.ts` | Vitest in jsdom with the `@/` alias and the Cobertura report |
| `frontend/.dockerignore`, `frontend/Dockerfile` | The image |
| `frontend/lib/config.ts` | `API_URL` from `NEXT_PUBLIC_API_URL` |
| `frontend/lib/types.ts` | The API's shapes: `User`, `Token`, `Note`, `Chat`, `Message`, `ChatDetail`, `MessageExchange` |
| `frontend/lib/session.ts` | The token in `sessionStorage`, with `subscribe` |
| `frontend/lib/validation.ts` | Form checks mirroring the API's limits |
| `frontend/lib/format.ts` | Timestamps for display |
| `frontend/lib/api.ts` | The one API client: timeouts, bearer header, `ApiError`, `NetworkError`, `errorMessage` |
| `frontend/components/Status.tsx` | `Loading` and `ErrorMessage` |
| `frontend/components/RequireAuth.tsx` | The signed-in gate and `useUser()` |
| `frontend/components/Header.tsx` | Nav and sign out |
| `frontend/components/SignInForm.tsx` | Register or sign in |
| `frontend/components/NoteForm.tsx`, `NoteItem.tsx` | Create or edit a note; one note with Edit, Delete (confirmed) and its Chats link |
| `frontend/components/ChatSidebar.tsx` | The note's chats: start, rename, delete (confirmed) |
| `frontend/components/MessageList.tsx`, `MessageComposer.tsx` | Messages oldest first; the send box |
| `frontend/app/layout.tsx`, `globals.css`, `page.tsx`, `health/route.ts`, `sign-in/page.tsx` | Root layout and styles, `/` → `/notes`, the healthcheck, the sign-in page |
| `frontend/app/(app)/layout.tsx`, `notes/page.tsx` | The signed-in group; the notes page |
| `frontend/app/(app)/notes/[noteId]/chats/ChatsProvider.tsx`, `layout.tsx`, `page.tsx`, `[chatId]/page.tsx` | The chats of one note, shared by sidebar and view; the chats page and the chat view |
| `frontend/lib/*.test.ts`, `frontend/components/*.test.tsx` | The tests |
| `docker-compose.yml`, `.env.example`, `.gitignore`, `.github/workflows/ci.yml` | The `frontend` service, its variables, Vitest's output ignored, the `frontend` CI job and the compose check |
| `docs/adr/0004-token-in-session-storage.md`, `README.md`, `AGENTS.md`, `frontend/README.md` | The decision, setup and next steps, the project facts |

---
### Task 1: Toolchain: manifest, TypeScript, lint, format and test setup

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/.node-version`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.ts`
- Create: `frontend/eslint.config.mjs`
- Create: `frontend/.prettierrc`
- Create: `frontend/.prettierignore`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/.dockerignore`
- Modify: `frontend/README.md`
- Modify: `.gitignore`

The first frontend change sets the pattern every later one is held to (`maintainability.md` rule 11): App Router, TypeScript strict, one API module, Vitest beside the code. The config mirrors what `create-next-app@16.4.3` writes, trimmed to what the app uses.
- [ ] **Step 1: Write the manifest and the runtime pin. Exact pins come from the lockfile `npm install` writes in the last step; `engines` is a floor because developers may run a newer Node than the image.**

`frontend/package.json`:

````json
{
  "name": "taskmind-frontend",
  "version": "0.1.0",
  "private": true,
  "engines": {
    "node": ">=24.22.2"
  },
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:coverage": "vitest run --coverage",
    "validate": "npm run lint && npm run format:check && npm run typecheck && npm run test"
  },
  "dependencies": {
    "next": "16.4.3",
    "react": "19.3.1",
    "react-dom": "19.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^7.0.1",
    "@testing-library/react": "^16.3.3",
    "@testing-library/user-event": "^14.6.8",
    "@types/node": "^24",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "@vitejs/plugin-react": "^6.1.2",
    "@vitest/coverage-v8": "^5.0.5",
    "eslint": "^10",
    "eslint-config-next": "16.4.3",
    "jsdom": "^30.1.3",
    "prettier": "3.9.10",
    "typescript": "^5",
    "vitest": "^5.0.5"
  }
}
````

`frontend/.node-version`:

````
24.22.2
````

- [ ] **Step 2: TypeScript strict with `noUncheckedIndexedAccess`, and the Next.js config with standalone output for the Dockerfile.**

`frontend/tsconfig.json`:

````json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"],
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": [
    "next-env.d.ts",
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts",
    "**/*.mts"
  ],
  "exclude": ["node_modules", ".next", "coverage"]
}
````

`frontend/next.config.ts`:

````ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Dockerfile copies .next/standalone, a self-contained server with only the modules it needs.
  output: "standalone",
};

export default nextConfig;
````

- [ ] **Step 3: ESLint from `eslint-config-next` with `no-console` as an error, and Prettier at the backend's line length.**

`frontend/eslint.config.mjs`:

````js
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // The assignment asks for no stray console output; errors reach the user through the UI.
      "no-console": "error",
    },
  },
  globalIgnores([".next/**", "out/**", "coverage/**", "next-env.d.ts"]),
]);

export default eslintConfig;
````

`frontend/.prettierrc`:

````json
{
  "printWidth": 100
}
````

`frontend/.prettierignore`:

````
.next
coverage
node_modules
package-lock.json
next-env.d.ts
````

- [ ] **Step 4: Vitest in jsdom: the `@/` alias, Testing Library's matchers, and the Cobertura report `diff-cover` reads.**

`frontend/vitest.config.ts`:

````ts
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // The same "@/..." alias tsconfig.json declares.
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules", ".next"],
    coverage: {
      provider: "v8",
      // Cobertura is what diff-cover reads in CI; text is for the terminal.
      reporter: ["text", "cobertura"],
      include: ["app/**", "components/**", "lib/**"],
      exclude: ["**/*.test.{ts,tsx}", "app/health/**"],
    },
  },
});
````

`frontend/vitest.setup.ts`:

````ts
import "@testing-library/jest-dom/vitest";
````

- [ ] **Step 5: Keep the build context small, replace the placeholder README, and ignore Vitest's output at the root.**

`frontend/.dockerignore`:

````
node_modules
.next
coverage
.env*
*.md
````

`frontend/README.md` becomes:

````markdown
# TaskMind frontend

Next.js app. Setup, commands and decisions are in the repository README.
````

`.gitignore` becomes:

````
# Environment and secrets
.env
.env.*
!.env.example

# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
htmlcov/

# Node / Next.js
node_modules/
.next/
out/
*.tsbuildinfo
npm-debug.log*
next-env.d.ts
coverage/

# Databases and dumps
*.sqlite
*.sqlite3
*.db
*.dump

# Editors and OS
.vscode/
.idea/
.DS_Store

# Agent skills installed locally with the skills CLI; not part of the project
.claude/skills/
skills-lock.json
````

- [ ] **Step 6: Install and lock. `package-lock.json` is committed; it is the pin `npm ci` and the Dockerfile use.**

````bash
cd frontend && npm install --no-audit --no-fund && npm run typecheck
````

`npm run typecheck` passes with no source yet; the lint and test steps come with the code they check.

### Task 2: Library modules: config, types, session, validation, the API client, and their tests

**Files:**
- Create: `frontend/lib/config.ts`
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/session.ts`
- Create: `frontend/lib/validation.ts`
- Create: `frontend/lib/format.ts`
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/validation.test.ts`
- Create: `frontend/lib/session.test.ts`
- Create: `frontend/lib/api.test.ts`

Everything a component needs from outside React, in `lib/`. No component calls `fetch` or touches storage directly (`maintainability.md` rule 5).
- [ ] **Step 1: The API address and the shapes the API returns.**

`frontend/lib/config.ts`:

````ts
// NEXT_PUBLIC_* values are inlined when `next build` runs, so the Docker image carries the URL it
// was built with (see the Dockerfile's build argument). The browser calls the API directly.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
````

`frontend/lib/types.ts`:

````ts
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
````

- [ ] **Step 2: The token store (ADR 0004). Reads survive a storage accessor that throws; `subscribe` is shaped for `useSyncExternalStore`.**

`frontend/lib/session.ts`:

````ts
// The bearer token lives in sessionStorage: it is gone when the tab closes, it is never sent by the
// browser on its own (so no cross-site request forgery handling is needed), and the API's CORS
// setup expects a bearer header, not a cookie. See docs/adr/0004-token-in-session-storage.md.

const TOKEN_KEY = "taskmind.token";

const listeners = new Set<() => void>();

function storage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    // Some privacy settings make the accessor itself throw. With no storage the user is simply
    // signed out, which RequireAuth turns into the sign-in page.
    return null;
  }
}

export function getToken(): string | null {
  return storage()?.getItem(TOKEN_KEY) ?? null;
}

export function setToken(token: string): void {
  storage()?.setItem(TOKEN_KEY, token);
  notify();
}

export function clearToken(): void {
  storage()?.removeItem(TOKEN_KEY);
  notify();
}

/** Subscribe to token changes made through this module. Shaped for `useSyncExternalStore`. */
export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notify(): void {
  for (const listener of listeners) {
    listener();
  }
}
````

- [ ] **Step 3: Form checks that copy the API's limits, and the timestamp formatter.**

`frontend/lib/validation.ts`:

````ts
// Form checks that mirror the API's Pydantic schemas, so a user hears about an empty or over-long
// field before a request is made. The API checks again; these limits are a copy, not the rule.

export const LIMITS = {
  noteTitle: 200,
  noteContent: 20_000,
  chatTitle: 100,
  message: 4000,
  passwordMin: 8,
  passwordMax: 128,
} as const;

/** The error for a field that must have text, after trimming, up to `max` characters. */
export function requiredText(value: string, max: number, label: string): string | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return `${label} is required`;
  }
  if (trimmed.length > max) {
    return `${label} must be at most ${max} characters`;
  }
  return null;
}

/** The error for a field that may be empty but has a ceiling. */
export function optionalText(value: string, max: number, label: string): string | null {
  if (value.length > max) {
    return `${label} must be at most ${max} characters`;
  }
  return null;
}

export function emailError(value: string): string | null {
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return "Email is required";
  }
  // Something@something.something; the API does the real check.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
    return "Enter a valid email address";
  }
  return null;
}

export function passwordError(value: string, forRegister: boolean): string | null {
  if (value.length === 0) {
    return "Password is required";
  }
  if (forRegister && value.length < LIMITS.passwordMin) {
    return `Password must be at least ${LIMITS.passwordMin} characters`;
  }
  if (value.length > LIMITS.passwordMax) {
    return `Password must be at most ${LIMITS.passwordMax} characters`;
  }
  return null;
}
````

`frontend/lib/format.ts`:

````ts
/** An ISO timestamp from the API in the reader's locale and time zone. */
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}
````

- [ ] **Step 4: The API client. Every call: bearer header when a token exists, `AbortSignal.timeout` (10 s; 100 s for a message, the API's worst case to OpenAI), no retry, `ApiError` carrying the API's `detail` (a string, or the `msg` items of a 422), `NetworkError` for no answer, and a 401 clearing the token.**

`frontend/lib/api.ts`:

````ts
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
````

- [ ] **Step 5: Tests. Validation at every edge; the session store and its listeners; the client with `fetch` stubbed at the boundary, covering the happy path, each error class, the 401 side effect and the message timeout.**

`frontend/lib/validation.test.ts`:

````ts
import { emailError, optionalText, passwordError, requiredText } from "@/lib/validation";

describe("requiredText", () => {
  it("rejects empty and whitespace-only text", () => {
    expect(requiredText("", 10, "Title")).toBe("Title is required");
    expect(requiredText("   ", 10, "Title")).toBe("Title is required");
  });

  it("accepts text up to the limit after trimming", () => {
    expect(requiredText("a", 10, "Title")).toBeNull();
    expect(requiredText(`  ${"x".repeat(10)}  `, 10, "Title")).toBeNull();
  });

  it("rejects text one past the limit", () => {
    expect(requiredText("x".repeat(11), 10, "Title")).toBe("Title must be at most 10 characters");
  });
});

describe("optionalText", () => {
  it("accepts empty text and text at the limit", () => {
    expect(optionalText("", 5, "Content")).toBeNull();
    expect(optionalText("abcde", 5, "Content")).toBeNull();
  });

  it("rejects text past the limit", () => {
    expect(optionalText("abcdef", 5, "Content")).toBe("Content must be at most 5 characters");
  });
});

describe("emailError", () => {
  it("requires an address with a domain", () => {
    expect(emailError("")).toBe("Email is required");
    expect(emailError("ada")).toBe("Enter a valid email address");
    expect(emailError("ada@example")).toBe("Enter a valid email address");
    expect(emailError(" ada@example.com ")).toBeNull();
  });
});

describe("passwordError", () => {
  it("requires a password", () => {
    expect(passwordError("", false)).toBe("Password is required");
  });

  it("applies the minimum only when registering", () => {
    expect(passwordError("short", false)).toBeNull();
    expect(passwordError("short", true)).toBe("Password must be at least 8 characters");
    expect(passwordError("12345678", true)).toBeNull();
  });

  it("rejects a password past the maximum", () => {
    expect(passwordError("x".repeat(129), false)).toBe("Password must be at most 128 characters");
  });
});
````

`frontend/lib/session.test.ts`:

````ts
import { clearToken, getToken, setToken, subscribe } from "@/lib/session";

beforeEach(() => {
  window.sessionStorage.clear();
});

describe("session", () => {
  it("starts with no token", () => {
    expect(getToken()).toBeNull();
  });

  it("stores and clears the token", () => {
    setToken("abc");
    expect(getToken()).toBe("abc");
    clearToken();
    expect(getToken()).toBeNull();
  });

  it("tells subscribers about every change until they unsubscribe", () => {
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    setToken("abc");
    clearToken();
    expect(listener).toHaveBeenCalledTimes(2);
    unsubscribe();
    setToken("def");
    expect(listener).toHaveBeenCalledTimes(2);
  });
});
````

`frontend/lib/api.test.ts`:

````ts
import { ApiError, MESSAGE_TIMEOUT_MS, NetworkError, api, errorMessage } from "@/lib/api";
import { getToken, setToken } from "@/lib/session";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  window.sessionStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function lastRequest(): { url: string; init: RequestInit } {
  const call = fetchMock.mock.calls.at(-1);
  if (call === undefined) {
    throw new Error("fetch was not called");
  }
  const [url, init] = call;
  return { url: String(url), init: init ?? {} };
}

describe("api", () => {
  it("posts JSON and returns the parsed body", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { access_token: "t", token_type: "bearer" }));

    const token = await api.login("ada@example.com", "secret");

    expect(token.access_token).toBe("t");
    const { url, init } = lastRequest();
    expect(url).toBe("http://localhost:8000/auth/login");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ email: "ada@example.com", password: "secret" }));
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  it("sends the stored token as a bearer header", async () => {
    setToken("abc");
    fetchMock.mockResolvedValue(jsonResponse(200, []));

    await api.listNotes();

    expect(new Headers(lastRequest().init.headers).get("Authorization")).toBe("Bearer abc");
  });

  it("sends no Authorization header without a token", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, []));

    await api.listNotes();

    expect(new Headers(lastRequest().init.headers).has("Authorization")).toBe(false);
  });

  it("returns nothing for a 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(api.deleteNote(1)).resolves.toBeUndefined();
    expect(lastRequest().init.method).toBe("DELETE");
  });

  it("throws an ApiError carrying the API's detail string", async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { detail: "Note not found" }));

    await expect(api.getNote(9)).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "Note not found",
    });
  });

  it("joins the messages of a 422 detail list", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(422, {
        detail: [
          { loc: ["body", "title"], msg: "String should have at least 1 character" },
          { loc: ["body", "content"], msg: "String should have at most 20000 characters" },
        ],
      }),
    );

    await expect(api.createNote("", "")).rejects.toThrow(
      "String should have at least 1 character; String should have at most 20000 characters",
    );
  });

  it("falls back to a generic message when the body is not JSON", async () => {
    fetchMock.mockResolvedValue(new Response("<html>", { status: 502 }));

    await expect(api.me()).rejects.toThrow("The server had a problem");
  });

  it("clears the token on a 401", async () => {
    setToken("expired");
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: "Not authenticated" }));

    await expect(api.me()).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBeNull();
  });

  it("keeps the token on other errors", async () => {
    setToken("fine");
    fetchMock.mockResolvedValue(jsonResponse(403, { detail: "Not the author" }));

    await expect(api.deleteNote(1)).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBe("fine");
  });

  it("turns a network failure into a NetworkError", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api.listNotes()).rejects.toMatchObject({
      name: "NetworkError",
      message: "Could not reach the server",
    });
  });

  it("names a timeout as such", async () => {
    fetchMock.mockRejectedValue(new DOMException("timed out", "TimeoutError"));

    await expect(api.listNotes()).rejects.toThrow("The server took too long to answer");
  });

  it("gives a message post the longer timeout", async () => {
    const timeoutSpy = vi.spyOn(AbortSignal, "timeout");
    fetchMock.mockResolvedValue(
      jsonResponse(201, {
        user_message: { id: 1, chat_id: 1, role: "user", content: "hi", created_at: "" },
        assistant_message: { id: 2, chat_id: 1, role: "assistant", content: "hi", created_at: "" },
      }),
    );

    await api.postMessage(1, "hi");

    expect(timeoutSpy).toHaveBeenLastCalledWith(MESSAGE_TIMEOUT_MS);
  });
});

describe("errorMessage", () => {
  it("shows the message of an ApiError or NetworkError", () => {
    expect(errorMessage(new ApiError(409, "Email already registered"))).toBe(
      "Email already registered",
    );
    expect(errorMessage(new NetworkError("Could not reach the server"))).toBe(
      "Could not reach the server",
    );
  });

  it("hides anything else behind a generic line", () => {
    expect(errorMessage(new Error("TypeError: x is undefined"))).toBe("Something went wrong");
    expect(errorMessage("string")).toBe("Something went wrong");
  });
});
````

- [ ] **Step 6: Check.**

````bash
cd frontend && npm run lint && npm run format:check && npm run typecheck && npx vitest run lib
````

Expect 3 files, 26 tests passing.

### Task 3: Components and their tests

**Files:**
- Create: `frontend/components/Status.tsx`
- Create: `frontend/components/RequireAuth.tsx`
- Create: `frontend/components/Header.tsx`
- Create: `frontend/components/SignInForm.tsx`
- Create: `frontend/components/NoteForm.tsx`
- Create: `frontend/components/NoteItem.tsx`
- Create: `frontend/components/MessageList.tsx`
- Create: `frontend/components/MessageComposer.tsx`
- Create: `frontend/components/ChatSidebar.tsx`
- Create: `frontend/components/SignInForm.test.tsx`
- Create: `frontend/components/NoteForm.test.tsx`
- Create: `frontend/components/MessageComposer.test.tsx`
- Create: `frontend/components/RequireAuth.test.tsx`

Semantic HTML throughout: every input has a `<label>`, every action is a `<button>` or a link, errors are `role="alert"`, loading lines `role="status"`. A form disables its submit while a request is in flight and shows the API's message when it fails.
- [ ] **Step 1: Loading and error lines with the ARIA roles screen readers announce.**

`frontend/components/Status.tsx`:

````tsx
export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <p role="status" className="status">
      {label}…
    </p>
  );
}

export function ErrorMessage({ message }: { message: string }) {
  return (
    <p role="alert" className="error">
      {message}
    </p>
  );
}
````

- [ ] **Step 2: The signed-in gate. The token comes through `useSyncExternalStore` so the server renders the loading line and the browser takes over without a hydration mismatch; the loaded user is keyed to the token it came from (the React compiler's lint rule refuses a `setState` reset inside the effect).**

`frontend/components/RequireAuth.tsx`:

````tsx
"use client";

// Wraps every signed-in page: no token means the sign-in page, a token means the user is loaded
// from /auth/me and handed down through `useUser`. The API still checks every request itself;
// this only decides what to render.

import { useRouter } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { ErrorMessage, Loading } from "@/components/Status";
import { api, errorMessage } from "@/lib/api";
import { getToken, subscribe } from "@/lib/session";
import type { User } from "@/lib/types";

const UserContext = createContext<User | null>(null);

interface Loaded {
  token: string;
  user: User | null;
  error: string | null;
}

export function useUser(): User {
  const user = useContext(UserContext);
  if (user === null) {
    throw new Error("useUser must be used inside RequireAuth");
  }
  return user;
}

// The server has no sessionStorage, so it renders the loading state and the browser takes over.
function serverToken(): null {
  return null;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const token = useSyncExternalStore(subscribe, getToken, serverToken);
  // Keyed to the token they came from, so a new token never shows the previous user or error.
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const user = loaded?.token === token ? loaded.user : null;
  const error = loaded?.token === token ? loaded.error : null;

  useEffect(() => {
    if (token === null) {
      router.replace("/sign-in");
      return;
    }
    let cancelled = false;
    api
      .me()
      .then((me) => {
        if (!cancelled) {
          setLoaded({ token, user: me, error: null });
        }
      })
      .catch((cause: unknown) => {
        // A 401 has already cleared the token, which re-runs this effect and redirects. Anything
        // else (the API down) is shown; there is nothing to retry automatically.
        if (!cancelled) {
          setLoaded({ token, user: null, error: errorMessage(cause) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, router]);

  if (token === null) {
    return <Loading label="Checking your session" />;
  }
  if (error !== null) {
    return <ErrorMessage message={error} />;
  }
  if (user === null) {
    return <Loading label="Loading your account" />;
  }
  return <UserContext.Provider value={user}>{children}</UserContext.Provider>;
}
````

- [ ] **Step 3: The header with sign out.**

`frontend/components/Header.tsx`:

````tsx
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useUser } from "@/components/RequireAuth";
import { clearToken } from "@/lib/session";

export function Header() {
  const user = useUser();
  const router = useRouter();

  function signOut() {
    clearToken();
    router.push("/sign-in");
  }

  return (
    <header className="header">
      <Link href="/notes" className="brand">
        TaskMind
      </Link>
      <nav aria-label="Main">
        <Link href="/notes">Notes</Link>
      </nav>
      <div className="header-user">
        <span>{user.email}</span>
        <button type="button" onClick={signOut}>
          Sign out
        </button>
      </div>
    </header>
  );
}
````

- [ ] **Step 4: Register or sign in: both fields labelled, errors tied to their field with `aria-describedby`, the API's message on refusal, the token stored and the user sent to `/notes`.**

`frontend/components/SignInForm.tsx`:

````tsx
"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";

import { ErrorMessage } from "@/components/Status";
import { api, errorMessage } from "@/lib/api";
import { setToken } from "@/lib/session";
import { emailError, passwordError } from "@/lib/validation";

type Mode = "sign-in" | "register";

interface FieldErrors {
  email?: string;
  password?: string;
}

export function SignInForm() {
  const router = useRouter();
  const ids = { email: useId(), password: useId() };
  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function switchMode() {
    setMode(mode === "sign-in" ? "register" : "sign-in");
    setFieldErrors({});
    setSubmitError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors: FieldErrors = {
      email: emailError(email) ?? undefined,
      password: passwordError(password, mode === "register") ?? undefined,
    };
    setFieldErrors(errors);
    setSubmitError(null);
    if (errors.email !== undefined || errors.password !== undefined) {
      return;
    }
    setPending(true);
    try {
      if (mode === "register") {
        await api.register(email.trim(), password);
      }
      const token = await api.login(email.trim(), password);
      setToken(token.access_token);
      router.push("/notes");
    } catch (cause: unknown) {
      setSubmitError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="form" aria-busy={pending}>
      <h2>{mode === "sign-in" ? "Sign in" : "Create an account"}</h2>
      <div className="field">
        <label htmlFor={ids.email}>Email</label>
        <input
          id={ids.email}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={fieldErrors.email !== undefined}
          aria-describedby={fieldErrors.email !== undefined ? `${ids.email}-error` : undefined}
        />
        {fieldErrors.email !== undefined && (
          <p id={`${ids.email}-error`} className="field-error">
            {fieldErrors.email}
          </p>
        )}
      </div>
      <div className="field">
        <label htmlFor={ids.password}>Password</label>
        <input
          id={ids.password}
          type="password"
          autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={fieldErrors.password !== undefined}
          aria-describedby={
            fieldErrors.password !== undefined ? `${ids.password}-error` : undefined
          }
        />
        {fieldErrors.password !== undefined && (
          <p id={`${ids.password}-error`} className="field-error">
            {fieldErrors.password}
          </p>
        )}
      </div>
      {submitError !== null && <ErrorMessage message={submitError} />}
      <div className="actions">
        <button type="submit" disabled={pending}>
          {mode === "sign-in" ? "Sign in" : "Register"}
        </button>
        <button type="button" className="link" onClick={switchMode} disabled={pending}>
          {mode === "sign-in" ? "Need an account? Register" : "Have an account? Sign in"}
        </button>
      </div>
    </form>
  );
}
````

- [ ] **Step 5: A note form for create and edit, and one note with its Edit, Delete (after `window.confirm`) and Chats link. Edit and Delete show only for the author; the API refuses anyone else regardless.**

`frontend/components/NoteForm.tsx`:

````tsx
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
````

`frontend/components/NoteItem.tsx`:

````tsx
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
````

- [ ] **Step 6: Messages oldest first, and the send box that keeps its text when the send fails.**

`frontend/components/MessageList.tsx`:

````tsx
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
````

`frontend/components/MessageComposer.tsx`:

````tsx
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
````

- [ ] **Step 7: The sidebar: the note's chats from `ChatsProvider` (Task 4), a form to start one, and per chat a rename form and a confirmed delete. Deleting the open chat goes back to the note's chats page.**

`frontend/components/ChatSidebar.tsx`:

````tsx
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
````

- [ ] **Step 8: Tests for the three forms: blocked when empty or over-long with no request made, submitted trimmed, and the failure path shown with the values kept.**

`frontend/components/SignInForm.test.tsx`:

````tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SignInForm } from "@/components/SignInForm";
import { getToken } from "@/lib/session";

const push = vi.fn();
const router = { push, replace: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  window.sessionStorage.clear();
  push.mockReset();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SignInForm", () => {
  it("blocks an empty submit and names both fields", async () => {
    const user = userEvent.setup();
    render(<SignInForm />);

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByText("Email is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("signs in, stores the token and goes to the notes", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ access_token: "tok", token_type: "bearer" }), { status: 200 }),
    );
    render(<SignInForm />);

    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "correct horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/notes"));
    expect(getToken()).toBe("tok");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows the API's message when sign-in is refused", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Incorrect email or password" }), { status: 401 }),
    );
    render(<SignInForm />);

    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
    expect(getToken()).toBeNull();
    expect(push).not.toHaveBeenCalled();
  });

  it("registers first, then signs in, when in register mode", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 1, email: "ada@example.com", created_at: "" }), {
          status: 201,
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "tok", token_type: "bearer" }), {
          status: 200,
        }),
      );
    render(<SignInForm />);

    await user.click(screen.getByRole("button", { name: "Need an account? Register" }));
    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.click(screen.getByRole("button", { name: "Register" }));
    expect(screen.getByText("Password must be at least 8 characters")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("Password"));
    await user.type(screen.getByLabelText("Password"), "long enough");
    await user.click(screen.getByRole("button", { name: "Register" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/notes"));
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls).toEqual([
      "http://localhost:8000/auth/register",
      "http://localhost:8000/auth/login",
    ]);
  });
});
````

`frontend/components/NoteForm.test.tsx`:

````tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { NoteForm } from "@/components/NoteForm";
import { ApiError } from "@/lib/api";

describe("NoteForm", () => {
  it("blocks a blank title and does not submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<NoteForm submitLabel="Create note" onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Title"), "   ");
    await user.click(screen.getByRole("button", { name: "Create note" }));

    expect(screen.getByText("Title is required")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("blocks a title over 200 characters", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<NoteForm submitLabel="Create note" onSubmit={onSubmit} />);

    await user.click(screen.getByLabelText("Title"));
    await user.paste("x".repeat(201));
    await user.click(screen.getByRole("button", { name: "Create note" }));

    expect(screen.getByText("Title must be at most 200 characters")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits the trimmed title and the content, then clears for the next note", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<NoteForm submitLabel="Create note" onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Title"), "  Groceries ");
    await user.type(screen.getByLabelText("Content"), "milk");
    await user.click(screen.getByRole("button", { name: "Create note" }));

    expect(onSubmit).toHaveBeenCalledWith({ title: "Groceries", content: "milk" });
    expect(screen.getByLabelText("Title")).toHaveValue("");
    expect(screen.getByLabelText("Content")).toHaveValue("");
  });

  it("keeps the values and shows the error when saving fails", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(403, "Not the author"));
    render(
      <NoteForm
        initial={{ title: "Old", content: "text" }}
        submitLabel="Save"
        onSubmit={onSubmit}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Not the author");
    expect(screen.getByLabelText("Title")).toHaveValue("Old");
  });
});
````

`frontend/components/MessageComposer.test.tsx`:

````tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MessageComposer } from "@/components/MessageComposer";
import { NetworkError } from "@/lib/api";

describe("MessageComposer", () => {
  it("blocks an empty message", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByText("Message is required")).toBeInTheDocument();
    expect(onSend).not.toHaveBeenCalled();
  });

  it("sends the trimmed text and clears the box", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<MessageComposer onSend={onSend} />);

    await user.type(screen.getByLabelText("Message"), "  What is this about?  ");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(onSend).toHaveBeenCalledWith("What is this about?");
    expect(screen.getByLabelText("Message")).toHaveValue("");
  });

  it("keeps the text and shows the error when sending fails", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockRejectedValue(new NetworkError("Could not reach the server"));
    render(<MessageComposer onSend={onSend} />);

    await user.type(screen.getByLabelText("Message"), "hello");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
    expect(screen.getByLabelText("Message")).toHaveValue("hello");
  });
});
````

- [ ] **Step 9: Tests for the gate, the refusals first (`testing.md` § The Elevated escalation): no token renders none of the page and goes to `/sign-in` with no request made; a 401 drops the token and goes there too; a token loads the user with the bearer header and renders the page; an API that cannot answer shows the failure.**

`frontend/components/RequireAuth.test.tsx`:

````tsx
import { render, screen, waitFor } from "@testing-library/react";

import { RequireAuth, useUser } from "@/components/RequireAuth";
import { getToken, setToken } from "@/lib/session";

const replace = vi.fn();
// One router object for the whole file, as Next's own hook returns: a fresh object on every
// render would re-run the gate's effect each time.
const router = { push: vi.fn(), replace };
vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  window.sessionStorage.clear();
  replace.mockReset();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function WhoAmI() {
  const user = useUser();
  return <p>Signed in as {user.email}</p>;
}

describe("RequireAuth", () => {
  it("sends a visitor with no token to sign in and renders none of the page", async () => {
    render(
      <RequireAuth>
        <WhoAmI />
      </RequireAuth>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/sign-in"));
    expect(screen.queryByText(/Signed in as/)).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("loads the user behind the token and renders the page", async () => {
    setToken("tok");
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ id: 1, email: "ada@example.com", created_at: "" }), {
        status: 200,
      }),
    );

    render(
      <RequireAuth>
        <WhoAmI />
      </RequireAuth>,
    );

    expect(await screen.findByText("Signed in as ada@example.com")).toBeInTheDocument();
    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer tok");
    expect(replace).not.toHaveBeenCalled();
  });

  it("drops a token the API rejects and goes to sign in", async () => {
    setToken("expired");
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not authenticated" }), { status: 401 }),
    );

    render(
      <RequireAuth>
        <WhoAmI />
      </RequireAuth>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/sign-in"));
    expect(getToken()).toBeNull();
    expect(screen.queryByText(/Signed in as/)).not.toBeInTheDocument();
  });

  it("shows the failure when the API cannot say who the user is", async () => {
    setToken("tok");
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    render(
      <RequireAuth>
        <WhoAmI />
      </RequireAuth>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
    expect(replace).not.toHaveBeenCalled();
  });
});
````

- [ ] **Step 10: Check. `ChatSidebar` imports `ChatsProvider` from Task 4, so lint and `tsc` pass only once Task 4 is in place; the tests here do not need it.**

````bash
cd frontend && npx vitest run components
````

Expect 4 files, 15 tests passing.

### Task 4: Pages and styles

**Files:**
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/globals.css`
- Create: `frontend/app/page.tsx`
- Create: `frontend/app/health/route.ts`
- Create: `frontend/app/sign-in/page.tsx`
- Create: `frontend/app/(app)/layout.tsx`
- Create: `frontend/app/(app)/notes/page.tsx`
- Create: `frontend/app/(app)/notes/[noteId]/chats/ChatsProvider.tsx`
- Create: `frontend/app/(app)/notes/[noteId]/chats/layout.tsx`
- Create: `frontend/app/(app)/notes/[noteId]/chats/page.tsx`
- Create: `frontend/app/(app)/notes/[noteId]/chats/[chatId]/page.tsx`

Every page that needs a user sits in the `(app)` group under `RequireAuth`. Pages are client components that load through `lib/api.ts` in an effect and render a loading line, an error line or the data; loaded state is keyed to the id it was loaded for.
- [ ] **Step 1: Root layout (system fonts, nothing to download before text shows), the stylesheet, `/` redirecting to `/notes`, the healthcheck route, and the sign-in page.**

`frontend/app/layout.tsx`:

````tsx
import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "TaskMind",
  description: "Shared notes, each with a private chat to an assistant that answers from the note.",
};

// System fonts only: nothing to download before text can show.
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
````

`frontend/app/page.tsx`:

````tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/notes");
}
````

`frontend/app/health/route.ts`:

````ts
// The Compose healthcheck calls this. The frontend has no dependency of its own to report: the
// browser talks to the API directly, so the API's /health covers that side.
export function GET(): Response {
  return Response.json({ status: "ok" });
}
````

`frontend/app/sign-in/page.tsx`:

````tsx
import { SignInForm } from "@/components/SignInForm";

export default function SignInPage() {
  return (
    <main className="main narrow">
      <h1>TaskMind</h1>
      <SignInForm />
    </main>
  );
}
````

`frontend/app/globals.css`:

````css
:root {
  --ink: #1f2430;
  --muted: #5c6370;
  --line: #d9dde3;
  --paper: #ffffff;
  --wash: #f4f5f7;
  --accent: #2b5fd9;
  --accent-ink: #ffffff;
  --danger: #b3261e;
  --radius: 6px;
}

* {
  box-sizing: border-box;
}

html {
  font-family:
    system-ui,
    -apple-system,
    "Segoe UI",
    Roboto,
    sans-serif;
  color: var(--ink);
  background: var(--wash);
  line-height: 1.5;
}

body {
  margin: 0;
}

h1,
h2,
h3 {
  line-height: 1.2;
  margin: 0 0 0.5rem;
}

h1 {
  font-size: 1.6rem;
}

h2 {
  font-size: 1.2rem;
}

h3 {
  font-size: 1.05rem;
}

a {
  color: var(--accent);
}

.header {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.75rem 1.5rem;
  background: var(--paper);
  border-bottom: 1px solid var(--line);
}

.brand {
  font-weight: 700;
  text-decoration: none;
  color: var(--ink);
}

.header-user {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--muted);
}

.main {
  max-width: 64rem;
  margin: 0 auto;
  padding: 1.5rem;
}

.main.narrow {
  max-width: 24rem;
}

section + section {
  margin-top: 2rem;
}

.form {
  display: grid;
  gap: 0.75rem;
  padding: 1rem;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.form.inline {
  padding: 0.75rem;
}

.field {
  display: grid;
  gap: 0.25rem;
}

label {
  font-weight: 600;
  font-size: 0.9rem;
}

input,
textarea {
  font: inherit;
  padding: 0.5rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper);
  color: var(--ink);
}

input:focus-visible,
textarea:focus-visible,
button:focus-visible,
a:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

[aria-invalid="true"] {
  border-color: var(--danger);
}

.field-error,
.error {
  color: var(--danger);
  margin: 0;
  font-size: 0.9rem;
}

.error {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--danger);
  border-radius: var(--radius);
  background: #fdf3f2;
}

.status,
.empty,
.meta {
  color: var(--muted);
  margin: 0.25rem 0;
  font-size: 0.9rem;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

button,
.button-link {
  font: inherit;
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius);
  border: 1px solid var(--accent);
  background: var(--accent);
  color: var(--accent-ink);
  cursor: pointer;
  text-decoration: none;
}

button:disabled {
  opacity: 0.6;
  cursor: default;
}

button.secondary,
.button-link {
  background: var(--paper);
  color: var(--accent);
}

button.danger {
  background: var(--paper);
  color: var(--danger);
  border-color: var(--danger);
}

button.link {
  background: none;
  border: none;
  color: var(--accent);
  padding: 0;
  text-decoration: underline;
}

.note-list,
.chat-list,
.messages {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.75rem;
}

.note {
  padding: 1rem;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}

.note-content {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.breadcrumb {
  color: var(--muted);
  margin-bottom: 0.5rem;
}

.chats-layout {
  display: grid;
  grid-template-columns: 18rem 1fr;
  gap: 1.5rem;
  align-items: start;
}

@media (max-width: 48rem) {
  .chats-layout {
    grid-template-columns: 1fr;
  }
}

.sidebar {
  display: grid;
  gap: 0.75rem;
}

.chat-row {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--paper);
  display: grid;
  gap: 0.4rem;
}

.chat-row.active {
  border-color: var(--accent);
}

.chat-row .actions button {
  padding: 0.2rem 0.5rem;
  font-size: 0.85rem;
}

.chat-main {
  display: grid;
  gap: 1rem;
}

.message {
  padding: 0.75rem;
  border-radius: var(--radius);
  background: var(--paper);
  border: 1px solid var(--line);
}

.message-user {
  border-left: 4px solid var(--accent);
}

.message-assistant {
  border-left: 4px solid var(--muted);
}

.message-role {
  font-weight: 600;
  font-size: 0.85rem;
}

.message p {
  margin: 0.25rem 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.composer {
  display: grid;
  gap: 0.5rem;
}
````

- [ ] **Step 2: The signed-in route group and the notes page: one `GET /notes` on load (the API's newest 50), create prepends, edit replaces, delete removes.**

`frontend/app/(app)/layout.tsx`:

````tsx
import type { ReactNode } from "react";

import { Header } from "@/components/Header";
import { RequireAuth } from "@/components/RequireAuth";

// Every page in this group needs a signed-in user.
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <Header />
      <main className="main">{children}</main>
    </RequireAuth>
  );
}
````

`frontend/app/(app)/notes/page.tsx`:

````tsx
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
````

- [ ] **Step 3: The chats of one note, shared by the sidebar and the chat view. The list is keyed to the note id; `reload` keeps the last list and shows the error when a refresh fails.**

`frontend/app/(app)/notes/[noteId]/chats/ChatsProvider.tsx`:

````tsx
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
````

- [ ] **Step 4: The chats layout (loads the note, holds the provider, renders the sidebar), the empty chats page, and the chat view: `GET /chats/{id}` on load, a post appends both halves of the exchange and reloads the sidebar so the chat moves to the top. `parseId` refuses anything but a positive integer.**

`frontend/app/(app)/notes/[noteId]/chats/layout.tsx`:

````tsx
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ChatsProvider } from "@/app/(app)/notes/[noteId]/chats/ChatsProvider";
import { ChatSidebar } from "@/components/ChatSidebar";
import { ErrorMessage, Loading } from "@/components/Status";
import { api, errorMessage } from "@/lib/api";
import type { Note } from "@/lib/types";

/** The note's id from the URL, or `null` when the segment is not a positive integer. */
export function parseId(segment: string | undefined): number | null {
  const id = Number(segment);
  return Number.isInteger(id) && id > 0 ? id : null;
}

export default function NoteChatsLayout({ children }: { children: ReactNode }) {
  const params = useParams<{ noteId: string }>();
  const noteId = parseId(params.noteId);
  const [note, setNote] = useState<Note | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (noteId === null) {
      return;
    }
    let cancelled = false;
    api
      .getNote(noteId)
      .then((loaded) => {
        if (!cancelled) {
          setNote(loaded);
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
  }, [noteId]);

  if (noteId === null) {
    return <ErrorMessage message="Note not found" />;
  }
  if (error !== null) {
    return <ErrorMessage message={error} />;
  }
  if (note === null) {
    return <Loading label="Loading note" />;
  }
  return (
    <ChatsProvider noteId={noteId}>
      <nav aria-label="Breadcrumb" className="breadcrumb">
        <Link href="/notes">Notes</Link> / <span>{note.title}</span>
      </nav>
      <h1>{note.title}</h1>
      <div className="chats-layout">
        <aside>
          <ChatSidebar noteId={noteId} />
        </aside>
        <section className="chat-main">{children}</section>
      </div>
    </ChatsProvider>
  );
}
````

`frontend/app/(app)/notes/[noteId]/chats/page.tsx`:

````tsx
export default function NoteChatsPage() {
  return (
    <>
      <h2>Ask about this note</h2>
      <p className="empty">Pick a chat on the left, or start a new one.</p>
    </>
  );
}
````

`frontend/app/(app)/notes/[noteId]/chats/[chatId]/page.tsx`:

````tsx
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
````

- [ ] **Step 5: Check: the whole validate script, the coverage report, and a production build.**

````bash
cd frontend && npm run validate && npm run test:coverage && NEXT_TELEMETRY_DISABLED=1 npm run build
````

Expect 7 test files, 41 tests passing, lines around 40% covered, and a build listing `/`, `/health`, `/notes`, `/notes/[noteId]/chats`, `/notes/[noteId]/chats/[chatId]` and `/sign-in`, with `.next/standalone/server.js` present.

Then with the API up (`docker compose up -d db backend` from the repo root), `npm run dev` and walk it in a browser: register, create a note, open its chats, start a chat, send a message, see the echo reply, rename and delete the chat, edit and delete the note.

### Task 5: Dockerfile, Compose service, variables and CI

**Files:**
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `.github/workflows/ci.yml`

The assignment's deliverable: `docker compose up --build` starts Postgres, the backend on :8000 and the frontend on :3000.
- [ ] **Step 1: The image: three stages, pinned base, `npm ci` from the lockfile in a cached layer, `NEXT_PUBLIC_API_URL` as a build argument, the standalone output as the runtime, non-root.**

`frontend/Dockerfile`:

````dockerfile
# Three stages: install from the lockfile, build, then a runtime image that holds only Next.js's
# standalone output. Node 24 LTS on Alpine, pinned by digest (node 24.22.2, npm 11.19.1).
FROM node:24-alpine@sha256:8a32c8cf649a49915a66e81e7a609223c708d0adabf288ee3f4077d765542f85 AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM deps AS build

# NEXT_PUBLIC_* values are inlined into the bundle here, so the image carries the API address it
# was built with. Compose passes it from .env.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY . .
RUN npm run build

FROM node:24-alpine@sha256:8a32c8cf649a49915a66e81e7a609223c708d0adabf288ee3f4077d765542f85 AS runner

WORKDIR /app
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NEXT_TELEMETRY_DISABLED=1

# The standalone build is a self-contained server with the modules it needs and nothing else.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static

USER node
EXPOSE 3000
CMD ["node", "server.js"]
````

- [ ] **Step 2: The Compose service: built with the API address the browser will use, waits for the backend, healthcheck on `/health` via 127.0.0.1 (busybox `wget` tries `::1` first and the server listens on IPv4).**

`docker-compose.yml` becomes:

````yaml
services:
  db:
    image: postgres:17.9-alpine@sha256:c7526c0f6c3f30260a563d7bcf8ad778effac59a44f8ffa86678c35418338609
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-taskmind}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is not set; copy .env.example to .env}
      POSTGRES_DB: ${POSTGRES_DB:-taskmind}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - taskmind_pgdata:/var/lib/postgresql/data
      - ./docker/postgres/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    environment:
      # Not the DATABASE_URL from .env: that one says localhost, for a developer's shell. Inside
      # the Compose network Postgres is the service `db` on its own port 5432.
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-taskmind}:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is not set; copy .env.example to .env}@db:5432/${POSTGRES_DB:-taskmind}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:3000}
      JWT_SECRET: ${JWT_SECRET:?JWT_SECRET is not set; see .env.example for how to generate one}
      JWT_EXPIRE_MINUTES: ${JWT_EXPIRE_MINUTES:-60}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      OPENAI_MODEL: ${OPENAI_MODEL:-gpt-6-luna}
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      # The slim image has no curl; urlopen raises on any non-2xx, which fails the check.
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  frontend:
    build:
      context: ./frontend
      args:
        # Inlined into the bundle at build time: the browser calls the API at this address, so it
        # is the host's view of the backend, not the Compose network's.
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}
    ports:
      - "${FRONTEND_PORT:-3000}:3000"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      # Alpine's busybox has wget; it exits non-zero on any non-2xx. 127.0.0.1, not localhost:
      # busybox tries ::1 first and the server listens on IPv4 only. 127.0.0.1, not localhost:
      # busybox tries ::1 first and the server listens on IPv4 only.
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:3000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

volumes:
  taskmind_pgdata:
````

- [ ] **Step 3: The variables, declared.**

`.env.example` becomes:

````
# Copy to .env and adjust. .env is gitignored.

# Postgres container (docker-compose.yml, service `db`)
POSTGRES_USER=taskmind
POSTGRES_PASSWORD=change-me-locally
POSTGRES_DB=taskmind
# Host port the container is published on. Change it if 5432 is taken, and match the URLs below.
POSTGRES_PORT=5432
# Host port the backend container is published on (docker compose up). Change it if 8000 is taken,
# and change NEXT_PUBLIC_API_URL to match.
BACKEND_PORT=8000
# Host port the frontend container is published on. Change it if 3000 is taken, and change
# CORS_ORIGINS to match.
FRONTEND_PORT=3000

# Frontend (frontend/lib/config.ts). Where the browser reaches the API. Baked into the frontend
# image when it is built, so a change needs `docker compose up --build`.
NEXT_PUBLIC_API_URL=http://localhost:8000

# Backend (backend/app/config.py). Host is localhost when the API runs outside Docker.
DATABASE_URL=postgresql+psycopg://taskmind:change-me-locally@localhost:5432/taskmind
CORS_ORIGINS=http://localhost:3000

# Tests (backend/tests) read only this variable. The database is "<POSTGRES_DB>_test", created by
# docker/postgres/init on first start; its name must end in _test or the suite refuses to run.
TEST_DATABASE_URL=postgresql+psycopg://taskmind:change-me-locally@localhost:5432/taskmind_test

# Sign-in. Generate a real secret with: python -c "import secrets; print(secrets.token_urlsafe(48))"
# The app refuses this placeholder and anything shorter than 32 characters.
JWT_SECRET=change-me-generate-a-real-secret-see-README
JWT_EXPIRE_MINUTES=60

# Assistant. Leave OPENAI_API_KEY empty and an echo answers instead of OpenAI, so the app runs
# without a key. The model is OpenAI's recommended cost-efficient one; change it here, not in code.
OPENAI_API_KEY=
OPENAI_MODEL=gpt-6-luna
````

- [ ] **Step 4: CI: a `frontend` job running `npm run validate` verbatim and the changed-line coverage with the same `diff-cover` the backend uses, and the `compose` job checking both `/health` endpoints.**

`.github/workflows/ci.yml` becomes:

````yaml
name: CI

on:
  pull_request:            # every pull request, whatever its base: a stacked PR must run CI too
  push:
    branches: [main]

permissions:
  contents: read

env:
  UV_VERSION: "0.11.24"

jobs:
  validate:
    name: validate
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
      - uses: astral-sh/setup-uv@d0d8abe699bfb85fec6de9f7adb5ae17292296ff # v6
        with:
          version: ${{ env.UV_VERSION }}
          enable-cache: true
          cache-dependency-glob: backend/uv.lock
      - name: Install
        run: cd backend && uv sync --locked
      - name: Validate
        # The backend half of the Validate command in AGENTS.md, verbatim.
        run: cd backend && uv run pytest tests/unit && uv run ruff check . && uv run ruff format --check . && uv run mypy

  integration:
    name: integration
    runs-on: ubuntu-24.04
    env:
      # Postgres is the same docker-compose.yml service a developer runs, so the image pin, the
      # healthcheck and the test-database init script live in one place. These are the values
      # Compose reads from .env locally; the password is a throwaway for a runner that lives
      # minutes. The test database is <POSTGRES_DB>_test, created by docker/postgres/init.
      POSTGRES_USER: taskmind
      POSTGRES_PASSWORD: taskmind
      POSTGRES_DB: taskmind
      POSTGRES_PORT: "5432"
      # Compose now needs it even to start db alone; the app's own check wants 32+ characters.
      JWT_SECRET: ci-only-secret-never-used-anywhere-real-0123456789
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@d0d8abe699bfb85fec6de9f7adb5ae17292296ff # v6
        with:
          version: ${{ env.UV_VERSION }}
          enable-cache: true
          cache-dependency-glob: backend/uv.lock
      - name: Install
        run: cd backend && uv sync --locked
      - name: Start Postgres
        run: docker compose up -d --wait db
      - name: Integration tests with changed-line coverage
        env:
          TEST_DATABASE_URL: postgresql+psycopg://${{ env.POSTGRES_USER }}:${{ env.POSTGRES_PASSWORD }}@localhost:${{ env.POSTGRES_PORT }}/${{ env.POSTGRES_DB }}_test
        run: cd backend && uv run pytest --cov=app --cov-report=xml && uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=20

  frontend:
    name: frontend
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
        with:
          fetch-depth: 0
      - uses: actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38 # v6.5.0
        with:
          node-version-file: frontend/.node-version
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - uses: astral-sh/setup-uv@d0d8abe699bfb85fec6de9f7adb5ae17292296ff # v6
        with:
          version: ${{ env.UV_VERSION }}
      - name: Install
        run: cd frontend && npm ci
      - name: Validate
        # The frontend half of the Validate command in AGENTS.md, verbatim.
        run: cd frontend && npm test && npm run lint && npm run format:check && npm run typecheck
      - name: Changed-line coverage
        # The same diff-cover the backend uses, over Vitest's Cobertura report.
        run: cd frontend && npm run test:coverage && uvx diff-cover coverage/cobertura-coverage.xml --compare-branch=origin/main --fail-under=20

  compose:
    name: compose
    runs-on: ubuntu-24.04
    env:
      POSTGRES_USER: taskmind
      POSTGRES_PASSWORD: taskmind
      POSTGRES_DB: taskmind
      POSTGRES_PORT: "5432"
      JWT_SECRET: ci-only-secret-never-used-anywhere-real-0123456789
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
      - name: Build and start every service
        # --wait returns non-zero unless every service reports healthy, so this is the
        # assignment's "docker compose up --build must start both apps" as a check.
        run: docker compose up --build -d --wait
      - name: Health
        run: |
          curl --fail --silent --show-error http://localhost:8000/health
          curl --fail --silent --show-error http://localhost:3000/health
      - name: Service logs
        if: always()
        run: docker compose logs backend frontend
      - name: Stop
        if: always()
        run: docker compose down -v
````

- [ ] **Step 5: Check from a clean copy of the branch, on ports that are free.**

````bash
POSTGRES_PORT=55433 BACKEND_PORT=8001 FRONTEND_PORT=3001 NEXT_PUBLIC_API_URL=http://localhost:8001 \
  CORS_ORIGINS=http://localhost:3001 COMPOSE_PROJECT_NAME=taskmind-scratch docker compose up --build -d --wait
curl --fail localhost:8001/health && curl --fail localhost:3001/health
curl -s -o /dev/null -w '%{http_code}\n' localhost:3001/sign-in     # 200
COMPOSE_PROJECT_NAME=taskmind-scratch docker compose down -v
````

Expect `--wait` to return with all three services healthy.

### Task 6: ADR 0004, README and AGENTS.md

**Files:**
- Create: `docs/adr/0004-token-in-session-storage.md`
- Modify: `README.md`
- Modify: `AGENTS.md`

What the next person reads first.
- [ ] **Step 1: The decision on where the token lives, in the ADR style the repo uses.**

`docs/adr/0004-token-in-session-storage.md`:

````markdown
# The browser keeps the bearer token in sessionStorage and calls the API directly

The frontend calls the API from the browser with the JWT in an `Authorization: Bearer` header, as the backend design decided, and keeps that token in `sessionStorage`. We considered an httpOnly cookie set by a Next.js route that proxies every call to the API, which keeps the token away from page scripts, and rejected it for now: it needs cross-site request forgery protection the bearer scheme does not, a second API address for the server side, and a proxy for every endpoint. `localStorage` was rejected because it outlives the tab, and the token already expires after an hour. The cost accepted: a script injected into the page could read the token, so the app renders text only through React and never with `dangerouslySetInnerHTML`. The cookie-and-proxy design is the next step if the app ever goes beyond a prototype.
````

- [ ] **Step 2: The README: the frontend in Structure and Prerequisites, Compose running all three, a section on running the frontend outside Docker with the pages described, the frontend tests, the decisions, and the "Unfinished and next steps" section the assignment asks for at the deadline.**

`README.md` becomes:

````markdown
# TaskMind

A small notes and chat app: a Next.js frontend and a FastAPI backend over PostgreSQL, run locally
with Docker Compose. Signed-in users share notes, and anyone can open a chat on a note to ask an AI
assistant about it.

## Structure

- `backend/` — FastAPI API, SQLAlchemy models, Alembic migrations, pytest tests
- `frontend/` — Next.js app, Vitest tests
- `docs/plans/` — design specs and implementation plans
- `docs/adr/` — decisions already taken; `GLOSSARY.md` — the domain language
- `docker/` — files mounted into Compose services

## Prerequisites

- Docker Desktop (Compose v2)
- [uv](https://docs.astral.sh/uv/) 0.11.24. It installs the pinned Python itself.
- Node.js 24.22.2 (`frontend/.node-version`) with npm, only to run the frontend outside Docker.

## Running everything with Docker

```bash
cp .env.example .env          # then set JWT_SECRET; the comment says how to generate one
docker compose up --build     # Postgres, the backend on :8000, then the frontend on :3000
```

Open http://localhost:3000, register with an email and a password of 8 or more characters, and you
are on the notes page. The backend container runs the migrations and then serves. `/health`
answers 200 once the database does, and the OpenAPI docs are at http://localhost:8000/docs. Data
lives on a named volume and survives `docker compose down`; `docker compose down -v` wipes it.
Logs are JSON on `docker compose logs -f backend`.

If a port is taken, set `POSTGRES_PORT`, `BACKEND_PORT` or `FRONTEND_PORT` in `.env`. For Postgres,
use the same port in `DATABASE_URL` and `TEST_DATABASE_URL`; for the backend, set
`NEXT_PUBLIC_API_URL` to match; for the frontend, set `CORS_ORIGINS` to match.

## Running the backend outside Docker

For development with reload and the tests:

```bash
docker compose up -d db       # Postgres only
cd backend && uv sync --locked
```

### Serving with reload

```bash
cd backend
uv run alembic upgrade head    # create or update the tables
uv run fastapi dev
```

The API is at http://localhost:8000 and the OpenAPI docs at http://localhost:8000/docs.

### Signing in

Set `JWT_SECRET` in `.env` first; the app refuses the placeholder. Then:

```bash
curl -s -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email": "ada@example.com", "password": "correct horse battery"}'
curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email": "ada@example.com", "password": "correct horse battery"}'
curl -s localhost:8000/auth/me -H "Authorization: Bearer <access_token>"
```

Tokens last `JWT_EXPIRE_MINUTES` (default 60). On `/docs`, the Authorize button takes the token.

### Notes

Every signed-in user sees every note; only the author can change or delete one.

```bash
TOKEN=<access_token>
curl -s -X POST localhost:8000/notes -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Plan", "content": "Ship the notes API"}'
curl -s 'localhost:8000/notes?limit=10&offset=0' -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/notes/1 -H "Authorization: Bearer $TOKEN"
curl -s -X PUT localhost:8000/notes/1 -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Plan", "content": "Shipped"}'
curl -s -X DELETE localhost:8000/notes/1 -H "Authorization: Bearer $TOKEN" -o /dev/null -w '%{http_code}\n'
```

`limit` is 1 to 100 (default 50). Changing someone else's note is a 403; a missing note is a 404.

### Chats

A chat belongs to one note and is private to the user who opened it. Posting a message stores it,
asks the assistant, and stores the reply. Without an `OPENAI_API_KEY` the assistant is an echo, so the
flow can be tried without a key.

```bash
curl -s -X POST localhost:8000/notes/1/chats -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Questions"}'
curl -s localhost:8000/notes/1/chats -H "Authorization: Bearer $TOKEN"
curl -s -X POST localhost:8000/chats/1/messages -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"content": "What is the plan?"}'
curl -s localhost:8000/chats/1 -H "Authorization: Bearer $TOKEN"
curl -s -X PUT localhost:8000/chats/1 -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"title": "Plan questions"}'
curl -s -X DELETE localhost:8000/chats/1 -H "Authorization: Bearer $TOKEN" -o /dev/null -w '%{http_code}\n'
```

A chat detail carries its most recent 200 messages, oldest first. Messages are at most 4000
characters. Another user's chat is a 403; if the assistant fails the reply is a 502 and nothing
is stored.

### The assistant

Set `OPENAI_API_KEY` in `.env` and the assistant answers through OpenAI, using only the note the
chat belongs to; `OPENAI_MODEL` picks the model. Leave the key empty and an echo answers instead,
so everything else can be tried without a key; the log says so once at the first message.

Each call has a 30-second timeout and at most two retries on transient errors. If it still fails,
the message post is a 502 and nothing is stored, so re-send it.

## Running the frontend outside Docker

With the backend up (in Docker or with `fastapi dev`):

```bash
cd frontend
npm ci
npm run dev                    # http://localhost:3000, reloads on save
```

The app reads `NEXT_PUBLIC_API_URL` at build time; it defaults to http://localhost:8000. The pages:

- `/sign-in` — register or sign in. The token is kept for the tab and dropped when it closes.
- `/notes` — every user's notes, newest first; create a note, and edit or delete your own, with a
  confirmation before a delete.
- `/notes/{id}/chats` — your chats on that note in a sidebar: start one, rename it, delete it.
- `/notes/{id}/chats/{chatId}` — the chat: its messages oldest first, and a box to ask the
  assistant. The reply appears under your message without a reload.

Every form refuses an empty title or message before anything is sent, and shows the API's own
message when a request fails. A 401 from the API sends you back to sign in.

Lint, format, type check and test:

```bash
cd frontend && npm run validate
```

### Changing the schema

Edit the models under `backend/app/models/`, then:

```bash
cd backend
uv run alembic revision --autogenerate -m "what changed"
```

Read the generated file under `backend/alembic/versions/`, check the names and `ondelete` rules,
and make sure `downgrade()` reverses `upgrade()`. Then `uv run alembic upgrade head`. The test
suite runs `alembic check`, so a model change without a migration fails CI.

## Running the tests

```bash
cd backend
uv run pytest tests/unit                 # no database needed
uv run pytest tests/integration          # needs `docker compose up -d db`; rebuilds the test database from the migrations
```

The integration suite reads `TEST_DATABASE_URL` from `.env` or the environment and refuses any
database whose name does not end in `_test`.

Lint, format and type check:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Frontend tests, with coverage:

```bash
cd frontend && npm run test:coverage
```

They run in jsdom with `fetch` stubbed, so no test needs the API. CI runs `npm run validate` and
`diff-cover` on the changed lines, and a `compose` job that builds all three services and checks
both `/health` endpoints.

## Decisions

See `docs/plans/2026-10-20-backend-design.md` and `docs/adr/`. In short:

- SQLAlchemy 2.0 (sync) with psycopg 3; separate Pydantic request and response schemas.
- Email + password sign-in with Argon2id hashing and short-lived JWT bearer tokens, behind one
  `get_current_user` dependency (ADR 0002).
- Every signed-in user can read every note; only the author edits or deletes it.
- Chats belong to a note and are private to the user who opened them; the assistant answers from
  that note's content only.
- JSON logs with an `X-Request-Id` on every request and response.
- The browser calls the API directly with the bearer token kept in `sessionStorage` (ADR 0004);
  all calls go through `frontend/lib/api.ts`, which bounds every wait and turns errors into
  messages. Chats live under their note in the UI, as in the API, so the assignment's `/chats`
  page is `/notes/{id}/chats`.

## Unfinished and next steps

Written at the deadline, 2026-10-30, and after it: the frontend was finished on 2026-11-02. What
is built: every backend endpoint with 146 tests, Docker for both apps, and a frontend that covers
sign-in, notes, chats and messages with loading, error and validation states. What is not:

- **The assistant has not been tried against OpenAI.** No key was available; the echo assistant
  answered every test. First thing with a key: post a message and read the `openai call` log line.
- **No frontend end-to-end test.** The forms and the API client have unit tests; nothing drives a
  browser through sign-in to a chat. Next: Playwright against `docker compose up`, run in CI.
- **No paging in the UI.** The API bounds every list; the notes page shows the newest 50 and the
  sidebar the 50 most recent chats. Next: a "load more" on each, using `limit` and `offset`.
- **No search by title**, the assignment's first bonus. The API would need a query parameter and
  an index on `lower(title)`.
- **Token in `sessionStorage`** (ADR 0004). Beyond a prototype, an httpOnly cookie with a Next.js
  proxy route, and a refresh token so the hour-long session does not end mid-chat.
- **A slow assistant holds a worker thread.** Each message waits up to 100 s in the API's
  threadpool; 40 slow calls at once would stall every request. Next: an async handler with
  `AsyncOpenAI`, or a queue.
- **No tracing of the assistant call** beyond one log line with tokens and latency. HD's standard
  is OpenInference spans in Arize Phoenix.
- **No login rate limit** and no account lockout.
- **Required status checks on `main`** are not configured on the repository yet.
- **No dependency-update bot** for either manifest; updates are by hand until Dependabot or Renovate
  is switched on.
````

- [ ] **Step 3: `AGENTS.md`: the frontend in the overview, the Validate, lint and type-check commands covering both apps, the Testing block with the frontend suites, the frontend's architecture lines, commands, the CI line, and two quirks (the inlined API URL; the React compiler's `setState`-in-effect rule).**

`AGENTS.md` becomes:

````markdown
# AGENTS.md
<!-- hd-skills REQUIRED SECTION: maintain-project-docs manages everything above the END marker -->
## Project Overview
TaskMind: shared notes with note-scoped AI chats. FastAPI + SQLAlchemy 2.0 + PostgreSQL backend in `backend/`; Next.js 16 (App Router, TypeScript strict) frontend in `frontend/`.
## Project Facts
- **Repo layout:** single-repo
- **Project type:** prototype
- **Components:**
  - backend — `backend/`
  - frontend — `frontend/`
- **Validate command:** `cd backend && uv run pytest tests/unit && uv run ruff check . && uv run ruff format --check . && uv run mypy && cd ../frontend && npm test && npm run lint && npm run format:check && npm run typecheck`
- **Lint / format command:** `cd backend && uv run ruff check --fix . && uv run ruff format . && cd ../frontend && npm run lint && npm run format`
- **Type check command:** `cd backend && uv run mypy && cd ../frontend && npm run typecheck`
- **Type check strictness:** `mypy --strict` (`strict = true` in `backend/pyproject.toml`); `tsc` with `strict` and `noUncheckedIndexedAccess` (`frontend/tsconfig.json`)
- **Plans & docs location:** `docs/plans/`
- **Cloud platform:** none
- **Cloud account owner:** none
- **Cloud guardrails:** none
- **Alerts channel:** none
- **Environments:** none
## Version control
- **Host:** github
- **Repo:** Nashit-HD/taskmind
- **PR tool:** gh CLI
- **Base branch:** main
- **Branch flow:** feature → main   # custom — nothing is deployed, so there is no develop or staging
- **Branch naming:** <type>/<slug>   # no ticket system
- **Automated reviewers:** none
- **Commit format:** conventional-commits
- **Merge method:** merge-commit
- **Required approvals:** 1   # reviewer: hiteshsalavi
## Testing
- **Framework:** pytest (backend), Vitest + Testing Library in jsdom (frontend)
- **Single target:** `cd backend && uv run pytest tests/unit/test_app.py`; frontend: `cd frontend && npx vitest run lib/api.test.ts`
- **Location / naming:** `backend/tests/{unit,integration}/test_*.py`, tests tree; `frontend/**/*.test.{ts,tsx}`, colocated. Suite commands run inside `backend/` or `frontend/`, as the Validate command does
- **Coverage target:** 20% — warns (prototype)
- **Suites:**
    - unit — `uv run pytest tests/unit` — gate
    - integration — `cd backend && uv run pytest --cov=app --cov-report=xml && uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=20` — ci
    - frontend-unit — `npm test` — gate
    - frontend-coverage — `cd frontend && npm run test:coverage && uvx diff-cover coverage/cobertura-coverage.xml --compare-branch=origin/main --fail-under=20` — ci
## Architecture & Structure
- `backend/app/main.py` — `create_app()`; the module-level `app` is served by `fastapi dev`/`fastapi run` via `[tool.fastapi]` in `pyproject.toml`
- `backend/app/config.py` — `Settings` from env, then the repo-root `.env`; `SettingsDep` for handlers
- `backend/app/logging.py` — JSON formatter, `X-Request-Id` middleware, one log line per request; pass fields as `extra={"fields": {...}}`
- `backend/app/assistant.py` — the `Assistant` protocol, `get_assistant` and `AssistantDep`; routers never call a provider directly. `build_assistant()` picks `OpenAIAssistant` when `OPENAI_API_KEY` is set, else `EchoAssistant`, once per process (cached); tests override the dependency or clear the cache
- `backend/app/pagination.py` — `LimitQuery`/`OffsetQuery`, the bounds every list endpoint shares
- `backend/app/routers/health.py` — `GET /health`, unauthenticated, 200 only when `SELECT 1` answers; the Compose healthcheck calls it
- `backend/Dockerfile` + `backend/entrypoint.sh` — pinned `python:3.13-slim`, deps from `uv.lock` with `--no-dev`, non-root; the entrypoint runs `alembic upgrade head` then `fastapi run`
- `frontend/lib/api.ts` — the one API client: every call adds the bearer token, has a timeout, and throws `ApiError` (the API's `detail`) or `NetworkError`; `errorMessage()` turns either into text for the UI
- `frontend/lib/session.ts` — the token in `sessionStorage` (ADR 0004) with `subscribe` for `useSyncExternalStore`; a 401 anywhere clears it
- `frontend/components/RequireAuth.tsx` — wraps the `app/(app)` route group: no token → `/sign-in`, else loads `/auth/me` and provides `useUser()`
- `frontend/app/(app)/notes/[noteId]/chats/` — chats live under their note: `layout.tsx` loads the note and holds `ChatsProvider` (the sidebar's list, shared with the chat view so a new message re-sorts it)
- `frontend/lib/validation.ts` — form checks that copy the API's limits; the API is the rule
- `frontend/Dockerfile` — pinned `node:24-alpine`, `npm ci`, `next build` with `output: "standalone"`, non-root `node` user; `NEXT_PUBLIC_API_URL` is a build argument
- Dependencies are `Annotated[..., Depends(...)]` aliases ending in `Dep`; handlers that touch the database are plain `def`
- Error shape is FastAPI's `{"detail": ...}` everywhere
- Observed through JSON logs on stdout (`docker compose logs backend`): one `info` line per request with `status` and `duration_ms`; a failure is an `error` line with `exception` and the same `request_id` the client received
## Key Commands
- Run everything: `docker compose up --build` (frontend on :3000, backend on :8000; needs a root `.env` with `POSTGRES_PASSWORD` and `JWT_SECRET`)
- Install: `cd backend && uv sync --locked`; `cd frontend && npm ci`
- Run API locally: `cd backend && uv run fastapi dev` (needs `db` up and a root `.env`)
- Run frontend locally: `cd frontend && npm run dev` (needs the API up)
- Database: `docker compose up -d db`; reset it: `docker compose down -v`
- Lint and format: `cd backend && uv run ruff check --fix . && uv run ruff format .`; `cd frontend && npm run lint && npm run format`
- Type check: `cd backend && uv run mypy`; `cd frontend && npm run typecheck`
- Unit tests: `cd backend && uv run pytest tests/unit`; `cd frontend && npm test`
- Integration tests: `cd backend && uv run pytest tests/integration` (needs `db` up)
## Workflows & Verification
- Before calling a change done, run the Validate command and read its output; run the integration suite when the change touches data or an endpoint
- CI (`.github/workflows/ci.yml`) runs the backend validate and integration jobs, the frontend validate and changed-line coverage, and a `compose` job that builds all three services, on every pull request
## Quirks & Gotchas
- ⚠️ **The test database is `<POSTGRES_DB>_test`, created by `docker/postgres/init/` only on a fresh volume** — if it is missing, `docker compose down -v` then `up -d db`.
- ⚠️ **Integration tests read only `TEST_DATABASE_URL` and refuse a database whose name does not end in `_test`** — set it in `.env` or the environment; unit tests need no database; the test process overrides `DATABASE_URL`.
- ⚠️ **Compose refuses to start without `POSTGRES_PASSWORD` and `JWT_SECRET`, even for `db` alone** — `cp .env.example .env` and set a real `JWT_SECRET`; `.env` is gitignored.
- ⚠️ **Port 5432 may be taken by another project's Postgres** — set `POSTGRES_PORT` in `.env` and use the same port in `DATABASE_URL` and `TEST_DATABASE_URL`.
- ⚠️ **`get_settings()` is cached** — a test that changes env must call `get_settings.cache_clear()` after.
- ⚠️ **`build_assistant()` is cached like `get_settings()`** — a test that sets `OPENAI_API_KEY` must clear both caches; `tests/conftest.py` unsets the key so no test ever calls OpenAI.
- ⚠️ **`NEXT_PUBLIC_API_URL` is baked into the frontend image** — after changing it, `docker compose up --build`. A new `FRONTEND_PORT` needs a matching `CORS_ORIGINS`.
- ⚠️ **Lint refuses `setState` directly in an effect** (React compiler rule) — key loaded state to its id instead of resetting it; see `RequireAuth.tsx`, `ChatsProvider.tsx`.
- ⚠️ **No AI attribution in commits or PR descriptions** — remove any `Co-Authored-By: Claude` or "Generated with" line before committing.
- ⚠️ **Read `GLOSSARY.md` and `docs/adr/` before changing the domain** — chats are private to their user (ADR 0003); use author, user, assistant, not owner, creator, bot.
<!-- END hd-skills REQUIRED SECTION: everything below is team-maintained; tooling never edits it -->

---

# Project Notes (team-maintained)

## Agent skills

### Issue tracker

Local markdown under `.scratch/<feature>/` (`spec.md` plus one `issues/NN-slug.md` per ticket). See `docs/agents/issue-tracker.md`.

### Triage labels

The default five roles (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
````


## Gaps against HD policy, recorded on purpose

- **No end-to-end test** (`testing.md` rule 12 names the user journey as the thing an e2e test proves). Unit tests cover the forms and the client; nothing drives a browser. Next: Playwright against `docker compose up`, as a `ci` suite.
- **No bundle-size ceiling declared** (`performance.md` rule 16, [warn]). Next 16's build prints no per-route sizes; next step is `@next/bundle-analyzer` or a size check on `.next/static` with a figure in `AGENTS.md`.
- **Two calls before the notes page shows** (`performance.md` rule 15, [warn]): `/auth/me` then `/notes`. Accepted for a prototype; the fix is caching the user beside the token.
- **The JSON the API returns is trusted as typed** (`maintainability.md` rule 12 asks for narrowing after parsing). `lib/api.ts` casts `response.json()` to the declared shape; the API in this repository is the contract, and a runtime validator would be a dependency for a shape that cannot drift unnoticed (the backend's tests pin it). Error bodies, which the UI shows, are narrowed field by field.
- **Token in `sessionStorage`** (ADR 0004): readable by any script on the page. Accepted for a prototype with no third-party script; the cookie-and-proxy design is the next step.

## Documentation Notes

- How the frontend is observed → **PR**: the Next.js server logs each request to stdout (`docker compose logs frontend`); in the browser every failed call renders a `role="alert"` with the API's `detail`; the API logs every call with the request id it returned, so a user's error line can be matched to a server log line by time and path. Failing looks like a red alert line in the page and a 4xx or 5xx on the API's request line.
- `NEXT_PUBLIC_API_URL` is fixed at build time, and `CORS_ORIGINS` must follow `FRONTEND_PORT` → **AGENTS.md** Quirks & Gotchas (Task 6), and **README** § Running everything with Docker.
- The React compiler lint rule `react-hooks/set-state-in-effect`, and the keyed-state pattern that satisfies it → **AGENTS.md** Quirks & Gotchas (Task 6); **code** comments in `RequireAuth.tsx`, `ChatsProvider.tsx` and the chat page.
- Where the token lives and why → **decision** `docs/adr/0004-token-in-session-storage.md` (Task 6).
- Chats are reached through their note in the UI, not a top-level `/chats` page → **README** § Decisions (Task 6), and **PR** as a departure from the assignment.
- The busybox `wget` healthcheck needs `127.0.0.1`, not `localhost` → **code** comment in `docker-compose.yml` (Task 5).
