import type { Message } from "./api";
import { plainMarkdown } from "./markdownPlain";

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

// A user message is drawn as Markdown only when it clearly has formatting, so "2*3*4" typed by hand stays as it is
const FORMATTED = /(^|\n)\s*(#{1,6} |[-*] |\d+\. |\|.*\||```|> )|\*\*\S[^\n]*\*\*|\$\$|\$[^$\n]+\$|\\\(|\\\[/;

export function looksFormatted(text: string): boolean {
  return FORMATTED.test(text);
}

// Builds the formatted copy from the drawn bubble: formulas become readable text that keeps its LaTeX in data-tex
function messageHtml(message: Message): string | null {
  const bubble = document.querySelector(`#message-${CSS.escape(message.id)} .bubble`);
  if (bubble === null) {
    return null;
  }
  const copy = bubble.cloneNode(true) as HTMLElement;
  copy.querySelectorAll(".message-attachment, .sources, .md-code-head, button, svg, img").forEach((element) => element.remove());
  copy.querySelectorAll<HTMLElement>(".math-inline, .math-block").forEach((span) => {
    const block = span.classList.contains("math-block");
    const formula = document.createElement(block ? "div" : "span");
    formula.textContent = span.dataset.plain ?? span.textContent ?? "";
    if (span.dataset.tex) {
      formula.dataset.tex = span.dataset.tex;
      if (block) formula.dataset.display = "block";
    }
    span.replaceWith(formula);
  });
  if (message.sources.length > 0) {
    const title = document.createElement("p");
    title.textContent = "Sumber:";
    const list = document.createElement("ol");
    for (const source of message.sources) {
      const item = document.createElement("li");
      if (source.url) {
        const link = document.createElement("a");
        link.href = source.url;
        link.textContent = source.title;
        item.append(link);
      } else {
        item.textContent = source.title;
      }
      list.append(item);
    }
    copy.append(title, list);
  }
  return `<meta charset="utf-8">${copy.innerHTML}`;
}

// The AI ends an answer with "[[lanjutan]]" and its follow-up questions, which the server turns into buttons;
// while the answer is still arriving that part, and a marker that is only half written, is hidden
const FOLLOW_UPS = /\n?[ \t]*[*_]{0,2}\[\[\s*lanjutan[\s\S]*$/i;
const HALF_MARKER = /\n[ \t]*[*_]{0,2}\[{1,2}[a-z]{0,8}$/i;

export function hideFollowUps(text: string): string {
  return text.replace(FOLLOW_UPS, "").replace(HALF_MARKER, "");
}

// The text of a message with its references, as Markdown for a downloaded file
function messageMarkdown(message: Message): string {
  const sources = message.sources.map((source, index) => `${index + 1}. ${source.title}${source.url ? ` - ${source.url}` : ""}`);
  return sources.length > 0 ? `${message.text}\n\nSumber:\n${sources.join("\n")}\n` : `${message.text}\n`;
}

// Saves a message as a Markdown file, named after the time it was sent
export function downloadMessage(message: Message) {
  const sent = new Date(message.sentAt);
  const two = (value: number) => String(value).padStart(2, "0");
  const stamp = Number.isNaN(sent.getTime())
    ? ""
    : `-${sent.getFullYear()}${two(sent.getMonth() + 1)}${two(sent.getDate())}-${two(sent.getHours())}${two(sent.getMinutes())}`;
  const url = URL.createObjectURL(new Blob([messageMarkdown(message)], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `vokapas${message.sender === "bot" ? "-jawaban" : "-pertanyaan"}${stamp}.md`;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Copies plain text such as one code block; false when the browser refuses
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// Copies a whole message, including its references; apps that accept formatting get bold, lists, and tables too
export async function copyMessage(message: Message): Promise<boolean> {
  const body = plainMarkdown(message.text);
  const sources = message.sources.map((source, index) => `${index + 1}. ${source.title}${source.url ? ` - ${source.url}` : ""}`);
  const text = sources.length > 0 ? `${body}\n\nSumber:\n${sources.join("\n")}` : body;
  const html = messageHtml(message);
  if (html !== null && typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          "text/plain": new Blob([text], { type: "text/plain" }),
          "text/html": new Blob([html], { type: "text/html" }),
        }),
      ]);
      return true;
    } catch {
      // some browsers only allow plain text
    }
  }
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
