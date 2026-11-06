import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { copyPlainMath, FORMULA, HAS_FORMULA, latexToPlain } from "./mathPlain";

type Katex = typeof import("katex").default;

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

// One formula drawn straight into its element. KaTeX places fractions and subscripts with inline styles:
// the site's Content-Security-Policy (style-src 'self') blocks style="" written in an HTML string,
// but allows styles set from script, which is what katex.render does.
// output "html" skips the hidden MathML copy, which made copied text come out one symbol per line;
// a formula KaTeX cannot read is shown as typed instead of breaking the message
function Formula({ source, display }: { source: string; display: boolean }) {
  const element = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    if (element.current !== null && katex !== null) {
      katex.render(source.trim(), element.current, { displayMode: display, output: "html", throwOnError: false });
    }
  }, [source, display]);

  return <span ref={element} className={display ? "math-block" : "math-inline"} data-plain={latexToPlain(source)} data-tex={source.trim()} />;
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
    parts.push(<Formula key={match.index} source={source} display={display !== undefined} />);
    last = match.index + match[0].length;
  }
  parts.push(text.slice(last).replaceAll("\\$", "$"));
  return parts;
}
