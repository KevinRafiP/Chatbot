import { formatValue, parseChart } from "./chartData";
import { plainMathText } from "./mathPlain";

const FENCE = /^\s*(`{3,}|~{3,})\s*([\w-]*)\s*$/;
const TABLE_DIVIDER = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;

// A chart becomes its title plus one "label: value" line per point, so the numbers survive a paste
function plainChart(source: string): string {
  const spec = parseChart(source);
  if (spec === null) return source;
  const lines = spec.labels.map((label, i) => `${label}: ${spec.series.map((item) => formatValue(item.values[i], spec.unit)).join(" / ")}`);
  const names = spec.series.length > 1 ? ` (${spec.series.map((item) => item.name).join(" / ")})` : "";
  return [`${spec.title || "Grafik"}${names}`, ...lines].join("\n");
}

// Markdown written as readable plain text, for copying and for previews: no **, #, or table dividers,
// table cells separated by tabs so they paste into a spreadsheet, and formulas as readable math
export function plainMarkdown(text: string): string {
  const out: string[] = [];
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const fence = FENCE.exec(lines[i]);
    if (fence) {
      const body: string[] = [];
      for (i++; i < lines.length && !lines[i].trim().startsWith(fence[1]); i++) body.push(lines[i]);
      out.push(fence[2].toLowerCase() === "chart" ? plainChart(body.join("\n")) : body.join("\n"));
      continue;
    }
    let line = lines[i];
    if (TABLE_DIVIDER.test(line) && line.includes("-")) continue;
    if (line.includes("|") && /^\s*\|/.test(line)) {
      line = line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim()).join("\t");
    }
    line = line
      .replace(/^\s{0,3}#{1,6}\s+/, "")
      .replace(/^(\s*)[*+]\s+/, "$1- ")
      .replace(/^\s{0,3}>\s?/, "")
      .replace(/\*\*(?=\S)(.+?)(?<=\S)\*\*/g, "$1")
      .replace(/~~(?=\S)(.+?)(?<=\S)~~/g, "$1")
      .replace(/(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])/g, "$1")
      .replace(/(?<![\p{L}\p{N}_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\p{L}\p{N}_])/gu, "$1")
      .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, "$1 ($2)")
      .replace(/`([^`\n]+)`/g, "$1");
    out.push(line);
  }
  return plainMathText(out.join("\n"));
}