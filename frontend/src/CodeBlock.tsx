import { useRef, useState } from "react";

// code longer than this many lines starts folded until the user opens it
const CODE_FOLD_LINES = 15;
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

// A code block; long code starts folded and opens or closes by sliding its height
export function CodeBlock({ code }: { code: string }) {
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
    return block;
  }
  return (
    <div className={`md-code-fold ${open ? "open" : ""}`}>
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
