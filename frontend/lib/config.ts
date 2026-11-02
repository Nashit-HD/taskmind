// NEXT_PUBLIC_* values are inlined when `next build` runs, so the Docker image carries the URL it
// was built with (see the Dockerfile's build argument). The browser calls the API directly.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
