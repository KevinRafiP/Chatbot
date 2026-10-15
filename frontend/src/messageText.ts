import type { Message } from "./api";

// Shows the time in the viewer's own timezone and language; older messages also get their date
export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const time = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return time;
  }
  const day = date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: date.getFullYear() === now.getFullYear() ? undefined : "numeric",
  });
  return `${day} ${time}`;
}

// Copies a whole message, including its references, so it can be pasted elsewhere
export async function copyMessage(message: Message): Promise<boolean> {
  const sources = message.sources.map((source, index) => `${index + 1}. ${source.title}${source.url ? ` - ${source.url}` : ""}`);
  const text = sources.length > 0 ? `${message.text}\n\nSumber:\n${sources.join("\n")}` : message.text;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
