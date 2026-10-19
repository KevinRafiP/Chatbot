import type { Message } from "./api";

// Made once and reused, because building a date formatter for every message is slow
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const dayFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
const dayYearFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });

// Shows the time in the viewer's own timezone and language; older messages also get their date
export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const time = timeFormat.format(date);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return time;
  }
  const day = (date.getFullYear() === now.getFullYear() ? dayFormat : dayYearFormat).format(date);
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
