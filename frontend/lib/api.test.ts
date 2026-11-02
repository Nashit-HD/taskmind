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
