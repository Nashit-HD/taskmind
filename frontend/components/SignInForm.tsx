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
