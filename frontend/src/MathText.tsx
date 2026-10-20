import { useEffect, useState } from "react";
import { copyPlainMath, FORMULA, HAS_FORMULA, latexToPlain } from "./mathPlain";

type Katex = typeof import("katex").default;

// The typing animation redraws the same formulas many times, so finished HTML is kept
const MAX_CACHED = 200;
const cache = new Map<string, string>();

// KaTeX is large, so it is only downloaded the first time an answer contains a formula
let katex: Katex | null = null;
let loading: Promise<void> | null = null;

document.addEventListener("copy", copyPlainMath);

function loadKatex(): Promise<void> {
  loading ??= Promise.all([import("katex"), import("katex/dist/katex.min.css")])
    .then(([module]) => {
      katex = module.default;
    })
    .catch(() => {
      // offline or blocked: formulas stay as typed, and the next answer tries again
      loading = null;
    });
  return loading;
}

// Draws one formula without the hidden MathML copy, which made copied text come out one symbol per line;
// a formula KaTeX cannot read is shown as typed instead of breaking the message
function formulaHtml(lib: Katex, source: string, display: boolean): string {
  const key = `${display ? "D" : "I"}${source}`;
  let html = cache.get(key);
  if (html === undefined) {
    html = lib.renderToString(source.trim(), { displayMode: display, output: "html", throwOnError: false });
    if (cache.size >= MAX_CACHED) {
      cache.delete(cache.keys().next().value!);
    }
    cache.set(key, html);
  }
  return html;
}

// Answer text with every LaTeX formula drawn as math; text without formulas is returned untouched
export function MathText({ text }: { text: string }) {
  const hasFormula = HAS_FORMULA.test(text);
  const [, setLoaded] = useState(katex !== null);

  useEffect(() => {
    if (hasFormula && katex === null) {
      loadKatex().then(() => setLoaded(katex !== null));
    }
  }, [hasFormula]);

  if (!hasFormula || katex === null) {
    return text;
  }

  const parts = [];
  let last = 0;
  for (const match of text.matchAll(FORMULA)) {
    const display = match[1] ?? match[2];
    const source = display ?? match[3] ?? match[4];
    parts.push(text.slice(last, match.index).replaceAll("\\$", "$"));
    parts.push(
      <span
        key={match.index}
        className={display !== undefined ? "math-block" : "math-inline"}
        data-plain={latexToPlain(source)}
        dangerouslySetInnerHTML={{ __html: formulaHtml(katex, source, display !== undefined) }}
      />,
    );
    last = match.index + match[0].length;
  }
  parts.push(text.slice(last).replaceAll("\\$", "$"));
  return parts;
}