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
