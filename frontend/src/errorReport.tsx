// Sends errors that happen in the browser to Sentry through its envelope endpoint, without the Sentry SDK.
// Off when VITE_SENTRY_DSN is empty; at most MAX_REPORTS per page load, and the same error only once
const MAX_REPORTS = 10;
const MAX_TEXT = 2000;

type Target = { url: string; dsn: string };

function readDsn(dsn: string): Target | null {
  try {
    const address = new URL(dsn);
    const parts = address.pathname.split("/").filter(Boolean);
    const project = parts.pop();
    if (!address.username || !project) return null;
    const prefix = parts.length > 0 ? `/${parts.join("/")}` : "";
    // the key goes in the query and the body is text/plain, so the browser sends it without a CORS preflight
    const url = `${address.protocol}//${address.host}${prefix}/api/${project}/envelope/?sentry_key=${address.username}&sentry_version=7&sentry_client=vokapas-web%2F1.0`;
    return { url, dsn };
  } catch {
    return null;
  }
}

function eventId(): string {
  return crypto.randomUUID().replace(/-/g, "");
}

// Stack lines as Sentry frames, oldest call first
function frames(stack: string) {
  return stack
    .split("\n")
    .map((line) => line.match(/(?:at\s+(?:(.+?)\s+\()?)?(https?:\/\/[^\s)]+):(\d+):(\d+)/))
    .filter((match): match is RegExpMatchArray => match !== null)
    .slice(0, 30)
    .map((match) => ({ function: match[1] ?? "?", filename: match[2], lineno: Number(match[3]), colno: Number(match[4]) }))
    .reverse();
}

export function startErrorReport() {
  const target = readDsn(import.meta.env.VITE_SENTRY_DSN ?? "");
  if (target === null) return;
  const seen = new Set<string>();

  function send(error: unknown, fallback: string) {
    const name = error instanceof Error ? error.name : "Error";
    const message = (error instanceof Error ? error.message : String(error ?? fallback)).slice(0, MAX_TEXT);
    const key = `${name}:${message}`;
    if (seen.size >= MAX_REPORTS || seen.has(key)) return;
    seen.add(key);
    const id = eventId();
    const now = new Date().toISOString();
    const event = {
      event_id: id,
      timestamp: now,
      platform: "javascript",
      level: "error",
      environment: import.meta.env.MODE,
      tags: { layanan: "frontend" },
      request: { url: window.location.origin + window.location.pathname, headers: { "User-Agent": navigator.userAgent } },
      exception: {
        values: [{ type: name, value: message, stacktrace: error instanceof Error && error.stack ? { frames: frames(error.stack) } : undefined }],
      },
    };
    const body = `${JSON.stringify({ event_id: id, sent_at: now, dsn: target!.dsn })}\n{"type":"event"}\n${JSON.stringify(event)}\n`;
    void fetch(target!.url, { method: "POST", body, headers: { "Content-Type": "text/plain;charset=UTF-8" }, keepalive: true }).catch(
      () => undefined,
    );
  }

  window.addEventListener("error", (event) => send(event.error ?? event.message, "Script error"));
  window.addEventListener("unhandledrejection", (event) => send(event.reason, "Unhandled rejection"));
}
