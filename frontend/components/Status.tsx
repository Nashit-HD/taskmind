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
