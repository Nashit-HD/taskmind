// The Compose healthcheck calls this. The frontend has no dependency of its own to report: the
// browser talks to the API directly, so the API's /health covers that side.
export function GET(): Response {
  return Response.json({ status: "ok" });
}
