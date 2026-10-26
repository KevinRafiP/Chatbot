import type { ReactNode } from "react";
import { Chart } from "./Chart";
import { MathText } from "./MathText";
import { FORMULA } from "./mathPlain";

const FENCE = /^\s*(`{3,}|~{3,})\s*([\w-]*)\s*$/;
const HEADING = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
const LIST_ITEM = /^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$/;
const QUOTE = /^\s{0,3}>\s?(.*)$/;
const TABLE_DIVIDER = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;
// Code spans and formulas are kept whole, so a "*" inside them is never read as bold or italic
const PROTECTED = new RegExp(`\`([^\`\\n]+)\`|${FORMULA.source}`, "g");
const INLINE =
  /\*\*(?=\S)([\s\S]+?)(?<=\S)\*\*|~~(?=\S)([\s\S]+?)(?<=\S)~~|\*(?=[^\s*])([\s\S]+?)(?<=[^\s*])\*|(?<![\p{L}\p{N}_])_(?=[^\s_])([\s\S]+?)(?<=[^\s_])_(?![\p{L}\p{N}_])|\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)|�(\d+)/u;

type Atom = { kind: "code" | "math"; text: string };
type ListLine = { indent: number; ordered: boolean; start: number; text: string };

// Bold, italic, strikethrough, inline code, links, and formulas inside one block of text
function renderInline(text: string): ReactNode[] {
  const atoms: Atom[] = [];
  const marked = text.replace(PROTECTED, (match, code: string | undefined) => {
    atoms.push(code !== undefined ? { kind: "code", text: code } : { kind: "math", text: match });
    return `�${atoms.length - 1}`;
  });
  let key = 0;

  function walk(source: string): ReactNode[] {
    const nodes: ReactNode[] = [];
    let rest = source;
    for (let match = INLINE.exec(rest); match !== null; match = INLINE.exec(rest)) {
      if (match.index > 0) nodes.push(rest.slice(0, match.index).replaceAll("\\$", "$"));
      const [whole, bold, strike, star, underscore, label, url, atom] = match;
      if (bold !== undefined) nodes.push(<strong key={key++}>{walk(bold)}</strong>);
      else if (strike !== undefined) nodes.push(<del key={key++}>{walk(strike)}</del>);
      else if (star !== undefined || underscore !== undefined) nodes.push(<em key={key++}>{walk(star ?? underscore)}</em>);
      else if (label !== undefined)
        nodes.push(
          <a key={key++} href={url} target="_blank" rel="noopener noreferrer">
            {walk(label)}
          </a>,
        );
      else {
        const item = atoms[Number(atom)];
        nodes.push(item.kind === "code" ? <code key={key++}>{item.text}</code> : <MathText key={key++} text={item.text} />);
      }
      rest = rest.slice(match.index + whole.length);
    }
    if (rest !== "") nodes.push(rest.replaceAll("\\$", "$"));
    return nodes;
  }
  return walk(marked);
}

// Reads the alignment of each column from the divider row, such as "|:---|---:|"
function tableAlign(divider: string): ("left" | "right" | "center")[] {
  return tableCells(divider).map((cell) => (cell.endsWith(":") ? (cell.startsWith(":") ? "center" : "right") : "left"));
}

// Splits "| a | b |" into its cells
function tableCells(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "");
  return trimmed.split(/(?<!\\)\|/).map((cell) => cell.trim().replaceAll("\\|", "|"));
}

function startsBlock(line: string, next: string | undefined): boolean {
  return (
    FENCE.test(line) ||
    HEADING.test(line) ||
    RULE.test(line) ||
    LIST_ITEM.test(line) ||
    QUOTE.test(line) ||
    (line.includes("|") && next !== undefined && TABLE_DIVIDER.test(next))
  );
}

// Nested lists follow the indentation of each item
function renderList(items: ListLine[], key: string): ReactNode {
  const first = items[0];
  const children: ReactNode[] = [];
  let i = 0;
  while (i < items.length) {
    const item = items[i];
    let j = i + 1;
    while (j < items.length && items[j].indent > item.indent) j++;
    const nested = items.slice(i + 1, j);
    children.push(
      <li key={i}>
        {renderInline(item.text)}
        {nested.length > 0 && renderList(nested, `${key}-${i}`)}
      </li>,
    );
    i = j;
  }
  return first.ordered ? (
    <ol key={key} start={first.start}>
      {children}
    </ol>
  ) : (
    <ul key={key}>{children}</ul>
  );
}

function renderBlocks(text: string, prefix = "b"): ReactNode[] {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  const key = () => `${prefix}${blocks.length}`;

  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") {
      i++;
      continue;
    }

    const fence = FENCE.exec(line);
    if (fence) {
      const body: string[] = [];
      let closed = false;
      for (i++; i < lines.length; i++) {
        const end = lines[i].trim();
        if (end.startsWith(fence[1][0].repeat(fence[1].length)) && end.replace(/[`~]/g, "") === "") {
          closed = true;
          i++;
          break;
        }
        body.push(lines[i]);
      }
      if (fence[2].toLowerCase() === "chart") {
        // the chart is drawn only once its data has fully arrived
        blocks.push(closed ? <Chart key={key()} source={body.join("\n")} /> : <div key={key()} className="chart-loading">Menyiapkan grafik...</div>);
      } else {
        blocks.push(
          <pre key={key()} className="md-code">
            <code>{body.join("\n")}</code>
          </pre>,
        );
      }
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      const Tag = heading[1].length <= 3 ? "h3" : "h4";
      blocks.push(
        <Tag key={key()} className="md-heading">
          {renderInline(heading[2])}
        </Tag>,
      );
      i++;
      continue;
    }

    if (RULE.test(line)) {
      blocks.push(<hr key={key()} />);
      i++;
      continue;
    }

    if (line.includes("|") && i + 1 < lines.length && TABLE_DIVIDER.test(lines[i + 1])) {
      const head = tableCells(line);
      const align = tableAlign(lines[i + 1]);
      const rows: string[][] = [];
      for (i += 2; i < lines.length && lines[i].includes("|") && lines[i].trim() !== ""; i++) {
        rows.push(tableCells(lines[i]));
      }
      blocks.push(
        <div key={key()} className="md-table">
          <table>
            <thead>
              <tr>
                {head.map((cell, c) => (
                  <th key={c} style={{ textAlign: align[c] }}>
                    {renderInline(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, r) => (
                <tr key={r}>
                  {head.map((_, c) => (
                    <td key={c} style={{ textAlign: align[c] }}>
                      {renderInline(row[c] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (LIST_ITEM.test(line)) {
      const items: ListLine[] = [];
      while (i < lines.length) {
        const item = LIST_ITEM.exec(lines[i]);
        if (item) {
          const ordered = /\d/.test(item[2]);
          items.push({ indent: item[1].length, ordered, start: ordered ? parseInt(item[2], 10) : 1, text: item[3] });
        } else if (lines[i].trim() !== "" && /^\s{2,}/.test(lines[i]) && items.length > 0) {
          items[items.length - 1].text += `\n${lines[i].trim()}`;
        } else {
          break;
        }
        i++;
      }
      blocks.push(renderList(items, key()));
      continue;
    }

    if (QUOTE.test(line)) {
      const quoted: string[] = [];
      for (let quote = QUOTE.exec(lines[i]); quote && i < lines.length; quote = QUOTE.exec(lines[++i] ?? "")) {
        quoted.push(quote[1]);
      }
      blocks.push(<blockquote key={key()}>{renderBlocks(quoted.join("\n"), `${key()}q`)}</blockquote>);
      continue;
    }

    // a paragraph runs until a blank line or a new block; a $$ formula over several lines stays in one piece
    const paragraph = [line];
    for (i++; i < lines.length; i++) {
      const openFormula = paragraph.join("\n").split("$$").length % 2 === 0;
      if (!openFormula && (lines[i].trim() === "" || startsBlock(lines[i], lines[i + 1]))) break;
      paragraph.push(lines[i]);
    }
    blocks.push(
      <p key={key()} className="md-paragraph">
        {renderInline(paragraph.join("\n"))}
      </p>,
    );
  }
  return blocks;
}

// An answer written in Markdown: headings, bold and italic text, lists, tables, code, formulas, and ```chart blocks.
// Text that is still arriving is fine too: an unfinished table, list, or chart is simply shown as far as it has come
export function Markdown({ text }: { text: string }) {
  return <div className="markdown">{renderBlocks(text)}</div>;
}