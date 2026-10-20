// $$...$$ and \[...\] are formulas on their own line; $...$ and \(...\) sit inside a sentence.
// A single $ has to touch its formula on both sides and must not be followed by a digit,
// so prices such as "$5 dan $10" stay plain text
export const FORMULA = /\n?\$\$([\s\S]+?)\$\$\n?|\n?\\\[([\s\S]+?)\\\]\n?|\\\(([\s\S]+?)\\\)|\$(?=\S)((?:\\\$|[^$\n])+?)(?<=\S)\$(?!\d)/g;
export const HAS_FORMULA = new RegExp(FORMULA.source);

const SYMBOLS: Record<string, string> = {
  times: "×", cdot: "·", div: "÷", pm: "±", mp: "∓", le: "≤", leq: "≤", ge: "≥", geq: "≥",
  ne: "≠", neq: "≠", approx: "≈", equiv: "≡", sim: "~", propto: "∝", infty: "∞", to: "→",
  rightarrow: "→", Rightarrow: "⇒", implies: "⇒", iff: "⇔", leftarrow: "←", circ: "°", degree: "°",
  in: "∈", notin: "∉", subset: "⊂", cup: "∪", cap: "∩", emptyset: "∅", forall: "∀", exists: "∃",
  angle: "∠", perp: "⊥", parallel: "∥", therefore: "∴", sum: "Σ", prod: "Π", int: "∫",
  partial: "∂", nabla: "∇", dots: "…", ldots: "…", cdots: "⋯", percent: "%",
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", varepsilon: "ε", theta: "θ",
  lambda: "λ", mu: "μ", pi: "π", rho: "ρ", sigma: "σ", tau: "τ", phi: "φ", varphi: "φ", omega: "ω",
  Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Pi: "Π", Sigma: "Σ", Phi: "Φ", Omega: "Ω",
  sin: "sin", cos: "cos", tan: "tan", log: "log", ln: "ln", exp: "exp", lim: "lim", min: "min", max: "max", mod: "mod",
};
const ROOTS: Record<string, string> = { "": "√", "3": "∛", "4": "∜" };
const SPACES = new Set([",", ";", ":", " ", "quad", "qquad"]);
const FRACTIONS = new Set(["frac", "dfrac", "tfrac"]);
// commands that only change the style of their content, so the content is kept as is
const STYLES = new Set(["text", "textbf", "textit", "mathrm", "mathbf", "mathit", "mathbb", "boldsymbol", "operatorname", "vec", "hat", "bar", "overline", "underline", "begin", "end"]);
const SKIPPED = new Set(["!", "left", "right", "displaystyle", "big", "Big", "bigg", "Bigg"]);

const SUPERSCRIPT: Record<string, string> = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "(": "⁽", ")": "⁾", n: "ⁿ", i: "ⁱ", "°": "°" };
const SUBSCRIPT: Record<string, string> = { "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋", "(": "₍", ")": "₎" };

// Reads one argument at position i: a {group}, a \command, or a single character
function argument(source: string, i: number): [string, number] {
  while (source[i] === " ") {
    i++;
  }
  if (source[i] === "{") {
    let depth = 0;
    for (let j = i; j < source.length; j++) {
      if (source[j] === "\\") {
        j++;
      } else if (source[j] === "{") {
        depth++;
      } else if (source[j] === "}" && --depth === 0) {
        return [source.slice(i + 1, j), j + 1];
      }
    }
    return [source.slice(i + 1), source.length];
  }
  const command = /^\\([a-zA-Z]+|.)/.exec(source.slice(i));
  const length = command ? command[0].length : 1;
  return [source.slice(i, i + length), i + length];
}

// A single number or name needs no brackets around it; anything longer does
function grouped(text: string): string {
  return /^[\p{L}\p{N}.,]+$/u.test(text) ? text : `(${text})`;
}

function script(text: string, table: Record<string, string>, mark: string): string {
  const chars = [...text];
  if (chars.every((char) => table[char])) {
    return chars.map((char) => table[char]).join("");
  }
  return `${mark}${grouped(text)}`;
}

function convert(source: string): string {
  let out = "";
  let i = 0;
  while (i < source.length) {
    const char = source[i];
    if (char === "\\") {
      const [token, next] = argument(source, i);
      const name = token.slice(1);
      i = next;
      if (FRACTIONS.has(name)) {
        const [top, afterTop] = argument(source, i);
        const [bottom, afterBottom] = argument(source, afterTop);
        i = afterBottom;
        out += `${grouped(convert(top))}/${grouped(convert(bottom))}`;
      } else if (name === "sqrt") {
        let degree = "";
        if (source[i] === "[") {
          const end = source.indexOf("]", i);
          degree = convert(source.slice(i + 1, end));
          i = end + 1;
        }
        const [inside, after] = argument(source, i);
        i = after;
        out += `${ROOTS[degree] ?? `${degree}√`}${grouped(convert(inside))}`;
      } else if (name === "pmod") {
        const [inside, after] = argument(source, i);
        i = after;
        out += ` (mod ${convert(inside)})`;
      } else if (STYLES.has(name)) {
        const [inside, after] = argument(source, i);
        i = after;
        out += name === "begin" || name === "end" ? "" : convert(inside);
      } else if (name === "\\") {
        out += "; ";
      } else if (SPACES.has(name)) {
        out += " ";
      } else if (SKIPPED.has(name)) {
        if (source[i] === ".") {
          i++;
        }
      } else {
        out += SYMBOLS[name] ?? name;
      }
    } else if (char === "^" || char === "_") {
      const [inside, after] = argument(source, i + 1);
      i = after;
      out += char === "^" ? script(convert(inside), SUPERSCRIPT, "^") : script(convert(inside), SUBSCRIPT, "_");
    } else if (char === "{") {
      const [inside, after] = argument(source, i);
      i = after;
      out += convert(inside);
    } else {
      out += char === "&" || char === "}" ? "" : char === "~" ? " " : char;
      i++;
    }
  }
  return out;
}

// A LaTeX formula as readable text, such as "\frac{1}{2} \times x^{2}" -> "1/2 × x²"
export function latexToPlain(source: string): string {
  return convert(source).replace(/ {2,}/g, " ").replace(/\( /g, "(").replace(/ \)/g, ")").trim();
}

// The whole answer with every formula turned into readable text, for copying
export function plainMathText(text: string): string {
  return text
    .replace(FORMULA, (_, block, bracket, paren, inline) => {
      const source = block ?? bracket ?? paren ?? inline;
      const plain = latexToPlain(source.replaceAll("\\$", "$"));
      return block !== undefined || bracket !== undefined ? `\n${plain}\n` : plain;
    })
    .replaceAll("\\$", "$");
}

// The formula element that holds this node, if any
function formulaOf(node: Node): Element | null {
  const element = node instanceof Element ? node : node.parentElement;
  return element?.closest("[data-plain]") ?? null;
}

// Copying selected text puts each formula's readable text on the clipboard instead of KaTeX's layout pieces
export function copyPlainMath(event: ClipboardEvent) {
  const selection = document.getSelection();
  if (!selection || selection.isCollapsed || !event.clipboardData) {
    return;
  }
  const box = document.createElement("div");
  for (let i = 0; i < selection.rangeCount; i++) {
    const range = selection.getRangeAt(i).cloneRange();
    // a selection that starts or ends inside a formula takes the whole formula
    const start = formulaOf(range.startContainer);
    const end = formulaOf(range.endContainer);
    if (start) {
      range.setStartBefore(start);
    }
    if (end) {
      range.setEndAfter(end);
    }
    box.append(range.cloneContents());
  }
  const formulas = box.querySelectorAll<HTMLElement>("[data-plain]");
  if (formulas.length === 0) {
    return;
  }
  formulas.forEach((formula) => {
    const plain = formula.dataset.plain ?? "";
    formula.replaceWith(formula.classList.contains("math-block") ? `\n${plain}\n` : plain);
  });
  // innerText needs the box on the page to keep line breaks, so it is placed off screen for a moment
  box.style.cssText = "position:fixed;left:-9999px;top:0;white-space:pre-wrap";
  document.body.append(box);
  const text = box.innerText;
  box.remove();
  event.clipboardData.setData("text/plain", text);
  event.preventDefault();
}