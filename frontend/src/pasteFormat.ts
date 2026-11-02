// Turns copied rich text (web pages, Word, Google Docs, other chat apps) into Markdown so its format survives the paste
const RICH_TAG = /<(h[1-6]|b|strong|em|i|u|s|del|ul|ol|table|a|code|pre|math|sup|sub|blockquote|hr)[\s>]|data-tex=/i;
const REMOVED = "script,style,meta,link,title,noscript,template,head,svg,img,button,.katex-html,mjx-container > :not(mjx-assistive-mml)";
const PARAGRAPH_TAGS = new Set(["P", "SECTION", "ARTICLE", "HEADER", "FOOTER", "MAIN", "ASIDE", "NAV", "FIGURE", "DL"]);
const LINE_TAGS = new Set(["DIV", "DT", "DD", "FIGCAPTION", "ADDRESS"]);

type Context = { pre: boolean; cell: boolean; depth: number };

function isBold(element: HTMLElement): boolean {
  const weight = element.style?.fontWeight ?? "";
  if (element.tagName === "B" || element.tagName === "STRONG") {
    // Google Docs wraps everything in a <b> that is not bold
    return weight !== "normal" && weight !== "400";
  }
  return weight === "bold" || Number(weight) >= 600;
}

function isItalic(element: HTMLElement): boolean {
  return element.tagName === "I" || element.tagName === "EM" || element.style?.fontStyle === "italic";
}

// Puts a marker around the words but keeps the spaces outside, because "** word**" is not bold in Markdown
function wrap(text: string, marker: string): string {
  const match = text.match(/^(\s*)([\s\S]*?)(\s*)$/);
  if (match === null || match[2] === "") {
    return text;
  }
  return `${match[1]}${marker}${match[2]}${marker}${match[3]}`;
}

// Short exponents stay readable as x^2, longer ones get brackets: x^(n+1)
function script(text: string, sign: string): string {
  const value = text.trim();
  if (value === "") {
    return "";
  }
  return /^[\w.]$/.test(value) || /^-?\d+$/.test(value) ? `${sign}${value}` : `${sign}(${value})`;
}

function mathToTex(element: Element): string {
  // Wikipedia wraps every formula in {\displaystyle ...}
  const tex = element
    .querySelector('annotation[encoding="application/x-tex"]')
    ?.textContent?.trim()
    .replace(/^\{\\displaystyle\s*([\s\S]*)\}$/, "$1");
  const display = element.getAttribute("display") === "block" || element.closest(".katex-display") !== null;
  if (!tex) {
    return (element.textContent ?? "").trim();
  }
  return display ? `\n\n$$${tex}$$\n\n` : `$${tex}$`;
}

function children(node: Node, context: Context): string {
  return Array.from(node.childNodes, (child) => convert(child, context)).join("");
}

function list(element: Element, context: Context): string {
  const ordered = element.tagName === "OL";
  let number = Number(element.getAttribute("start") ?? 1) || 1;
  const indent = "   ".repeat(context.depth);
  const lines: string[] = [];
  for (const item of Array.from(element.children)) {
    if (item.tagName !== "LI") {
      continue;
    }
    const marker = ordered ? `${number++}. ` : "- ";
    const body = children(item, { ...context, depth: context.depth + 1 })
      .replace(/\n{2,}/g, "\n")
      .trim();
    lines.push(`${indent}${marker}${body}`);
  }
  return `\n\n${lines.join("\n")}\n\n`;
}

function table(element: HTMLTableElement, context: Context): string {
  const rows = Array.from(element.rows, (row) =>
    Array.from(row.cells, (cell) => children(cell, { ...context, cell: true }).replace(/\s+/g, " ").replace(/\|/g, "\\|").trim()),
  ).filter((row) => row.length > 0);
  if (rows.length === 0) {
    return "";
  }
  const width = Math.max(...rows.map((row) => row.length));
  const line = (row: string[]) => `| ${Array.from({ length: width }, (_, index) => row[index] ?? "").join(" | ")} |`;
  const divider = `| ${Array(width).fill("---").join(" | ")} |`;
  return `\n\n${[line(rows[0]), divider, ...rows.slice(1).map(line)].join("\n")}\n\n`;
}

function convert(node: Node, context: Context): string {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent ?? "";
    return context.pre ? text : text.replace(/\s+/g, " ");
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return "";
  }

  const element = node as HTMLElement;
  // MathML tags keep their lowercase name inside an HTML page
  const tag = element.tagName.toUpperCase();
  if (tag === "MATH") {
    return mathToTex(element);
  }
  // formulas copied from Vokapas carry their LaTeX source
  if (element.dataset?.tex) {
    return element.dataset.display === "block" ? `\n\n$$${element.dataset.tex}$$\n\n` : `$${element.dataset.tex}$`;
  }
  if (element.style?.display === "none" && !element.querySelector("math")) {
    return "";
  }
  if (tag === "BR") {
    return context.cell ? " " : "\n";
  }
  if (tag === "HR") {
    return "\n\n---\n\n";
  }
  if (/^H[1-6]$/.test(tag)) {
    return `\n\n${"#".repeat(Number(tag[1]))} ${children(element, context).trim()}\n\n`;
  }
  if (tag === "UL" || tag === "OL") {
    return list(element, context);
  }
  if (tag === "TABLE") {
    return table(element as HTMLTableElement, context);
  }
  if (tag === "PRE") {
    const language = element.querySelector("code")?.className.match(/language-(\w+)/)?.[1] ?? "";
    const code = (element.textContent ?? "").replace(/\n$/, "");
    return `\n\n\`\`\`${language}\n${code}\n\`\`\`\n\n`;
  }
  if (tag === "CODE") {
    const code = (element.textContent ?? "").replace(/\s+/g, " ");
    return code.trim() === "" ? code : `\`${code}\``;
  }
  if (tag === "BLOCKQUOTE") {
    const body = children(element, context).trim().replace(/\n{3,}/g, "\n\n");
    return `\n\n${body.split("\n").map((line) => `> ${line}`).join("\n")}\n\n`;
  }
  if (tag === "SUP" || tag === "SUB") {
    return script(children(element, context), tag === "SUP" ? "^" : "_");
  }

  let text = children(element, context);
  if (tag === "A") {
    const href = element.getAttribute("href") ?? "";
    const label = text.trim();
    if (/^https?:\/\//i.test(href) && label !== "" && label !== href) {
      text = text.replace(label, `[${label}](${href})`);
    }
  }
  if (tag === "S" || tag === "DEL" || tag === "STRIKE") {
    text = wrap(text, "~~");
  }
  if (isItalic(element)) {
    text = wrap(text, "*");
  }
  if (isBold(element)) {
    text = wrap(text, "**");
  }
  if (PARAGRAPH_TAGS.has(tag)) {
    return `\n\n${text.trim()}\n\n`;
  }
  if (LINE_TAGS.has(tag)) {
    return `\n${text.trim()}\n`;
  }
  return text;
}

// Removes stray spaces left by the HTML layout, except inside code blocks and in front of nested list items
function tidy(markdown: string): string {
  let inCode = false;
  const lines = markdown.split("\n").map((line) => {
    if (line.startsWith("```")) {
      inCode = !inCode;
      return line;
    }
    if (inCode) {
      return line;
    }
    return /^\s*(- |\d+\. )/.test(line) ? line.trimEnd() : line.trim();
  });
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

// Returns null when the copied HTML carries no formatting, so the browser's normal plain-text paste is used
export function htmlToMarkdown(html: string): string | null {
  if (!RICH_TAG.test(html) && !/font-weight:\s*(bold|[6-9]00)|font-style:\s*italic/i.test(html)) {
    return null;
  }
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll(REMOVED).forEach((element) => element.remove());
  const markdown = tidy(convert(doc.body, { pre: false, cell: false, depth: 0 }));
  return markdown === "" ? null : markdown;
}