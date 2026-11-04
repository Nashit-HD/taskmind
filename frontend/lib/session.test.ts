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
