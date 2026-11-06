const FENCE_LINE = /^\s*(`{3,}|~{3,})/;
const TABLE_DIVIDER = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;
// a block marker typed without its text yet, such as "##", "-", or "1."
const BARE_MARKER = /^\s{0,3}(#{1,6}|-{1,2}|\*{1,2}|[+>]|\d{1,3}[.)]|[`~]{1,2})\s*$/;
// a link whose address is still arriving: "[label](https://exa"
const OPEN_LINK = /\[([^\]\n]+)\]\([^)\s]*$/;

// Closes the bold, italic, strikethrough, and code marks that the last line opened but did not close yet
function closeInline(line: string): string {
  // code spans are hidden first, so a "*" inside them is not read as a mark
  const masked = line.replace(/`[^`]+`/g, (code) => "x".repeat(code.length));
  const openCode = masked.indexOf("`");
  const scanEnd = openCode === -1 ? masked.length : openCode;
  const stack: { mark: string; at: number }[] = [];

  for (let i = 0; i < scanEnd; i++) {
    const pair = masked.slice(i, i + 2);
    const mark = pair === "**" || pair === "~~" ? pair : masked[i] === "*" ? "*" : "";
    if (mark === "") continue;
    const before = masked[i - 1] ?? " ";
    const after = masked[i + mark.length] ?? "";
    if (stack.length > 0 && stack[stack.length - 1].mark === mark && /\S/.test(before)) {
      stack.pop();
    } else if (after === "" || /\S/.test(after)) {
      // a mark between spaces ("2 * 3") or right after a letter or digit ("2**3", "a*b") opens nothing
      if (!/[\p{L}\p{N}]/u.test(before)) stack.push({ mark, at: i });
    }
    i += mark.length - 1;
  }

  let text = openCode === -1 ? line : line.slice(0, openCode);
  let code = openCode === -1 ? "" : line.slice(openCode + 1);
  // a mark with nothing after it yet is hidden until its text arrives
  while (code === "" && stack.length > 0 && text.trimEnd().length === stack[stack.length - 1].at + stack[stack.length - 1].mark.length) {
    text = text.slice(0, stack.pop()!.at);
  }
  if (openCode !== -1 && code.trim() === "") code = "";
  // "**bold*" is half of a closing "**": the lone "*" is dropped and the pair is added below
  const top = stack[stack.length - 1]?.mark ?? "";
  if (code === "" && top.length === 2 && text.endsWith(top[0]) && !text.endsWith(top)) text = text.slice(0, -1);
  const tail = text.slice(text.trimEnd().length);
  const closing = stack.map((item) => item.mark).reverse().join("");
  if (code !== "") return `${text}\`${code}\`${closing}`;
  return `${text.slice(0, text.length - tail.length)}${closing}${tail}`;
}

// Markdown that is still being typed, made to read as finished: open marks are closed, a lone "##" or "-" is hidden,
// and a table header gets its divider early, so the reader never sees the raw symbols for a moment
export function closeMarkdown(text: string): string {
  const lines = text.split("\n");
  const fences = lines.filter((line) => FENCE_LINE.test(line)).length;
  // inside an unfinished code block everything is code, so nothing needs closing
  if (fences % 2 === 1) return text;

  let last = lines[lines.length - 1];
  if (BARE_MARKER.test(last)) {
    lines[lines.length - 1] = "";
    return lines.join("\n");
  }

  const previous = lines[lines.length - 2] ?? "";
  const beforePrevious = lines[lines.length - 3] ?? "";
  const isRow = (line: string) => line.trim().startsWith("|");
  // the header row is complete and the divider has not come or has only started, such as "|" or "|--"
  if (isRow(previous) && !isRow(beforePrevious) && /^\s*(\|[\s|:-]*)?$/.test(last) && !TABLE_DIVIDER.test(last)) {
    lines[lines.length - 1] = divider(previous);
    return lines.join("\n");
  }

  last = closeInline(last.replace(OPEN_LINK, "$1"));
  lines[lines.length - 1] = last;
  // the header row is still being typed
  if (isRow(last) && !isRow(previous)) lines.push(divider(last));
  return lines.join("\n");
}

function divider(header: string): string {
  const cells = header.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").length;
  return `|${" --- |".repeat(Math.max(cells, 1))}`;
}
