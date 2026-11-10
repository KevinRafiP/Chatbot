import { useEffect, useRef, useState } from "react";
import { copyText } from "./messageText";

// code longer than this many lines starts folded until the user opens it
const CODE_FOLD_LINES = 15;
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
const COPIED_MS = 1500;

// The bar above a code block: its language and a button that copies the whole code, even while it is folded
function CodeHeader({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState<boolean | null>(null);

  useEffect(() => {
    if (copied === null) {
      return;
    }
    const timer = window.setTimeout(() => setCopied(null), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  return (
    <div className="md-code-head">
      <span className="md-code-lang">{language || "kode"}</span>
      <button
        type="button"
        className="md-code-copy"
        onClick={async (event) => {
          event.stopPropagation();
          setCopied(await copyText(code));
        }}
        aria-label="Salin kode"
      >
        {copied === null ? "Salin" : copied ? "Tersalin" : "Gagal menyalin"}
      </button>
    </div>
  );
}

// A code block with a copy button; long code starts folded and opens or closes by sliding its height
export function CodeBlock({ code, language = "" }: { code: string; language?: string }) {
  const lineCount = code.split("\n").length;
  const long = lineCount > CODE_FOLD_LINES;
  const [open, setOpen] = useState(false);
  // the height to slide to; null once fully open, so code that is still arriving is never cut off
  const [height, setHeight] = useState<number | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  function toggle() {
    const box = boxRef.current;
    if (box === null) {
      return;
    }
    const instant = window.matchMedia(REDUCED_MOTION_QUERY).matches;
    if (open) {
      // slides from the real height, because nothing can slide from "no limit"
      setHeight(box.scrollHeight);
      requestAnimationFrame(() => requestAnimationFrame(() => setOpen(false)));
    } else {
      setHeight(instant ? null : box.scrollHeight);
      setOpen(true);
    }
  }

  const block = (
    <pre className="md-code">
      <code>{code}</code>
    </pre>
  );
  if (!long) {
    return (
      <div className="md-code-wrap">
        <CodeHeader code={code} language={language} />
        {block}
      </div>
    );
  }
  return (
    <div className={`md-code-wrap md-code-fold ${open ? "open" : ""}`}>
      <CodeHeader code={code} language={language} />
      <div
        ref={boxRef}
        className="md-code-box"
        style={open ? (height === null ? undefined : { maxHeight: height }) : undefined}
        onTransitionEnd={() => open && setHeight(null)}
      >
        {block}
      </div>
      <button type="button" className="md-code-toggle" onClick={toggle} aria-expanded={open}>
        {open ? "Lipat kode" : `Tampilkan semua (${lineCount} baris)`}
      </button>
    </div>
  );
}
