import { useEffect, useState } from "react";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
// at least this many characters per frame, about 120 per second
const MIN_STEP = 2;
// a bigger backlog is shown faster, so the text never falls far behind the stream
const CATCH_UP = 10;

// Streamed text arrives in uneven bursts; this shows it a few characters per frame so it reads as steady typing
export function useSmoothText(text: string): string {
  const [length, setLength] = useState(0);

  useEffect(() => {
    if (length === text.length) {
      return;
    }
    const frame = requestAnimationFrame(() => {
      setLength((current) => {
        // the answer started over, or the user prefers no motion
        if (current > text.length || window.matchMedia(REDUCED_MOTION_QUERY).matches) {
          return text.length;
        }
        const step = Math.max(MIN_STEP, Math.ceil((text.length - current) / CATCH_UP));
        return Math.min(current + step, text.length);
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [length, text.length]);

  let end = Math.min(length, text.length);
  // never cut an emoji in half, which would show a broken symbol for a frame
  const last = text.charCodeAt(end - 1);
  if (last >= 0xd800 && last <= 0xdbff) {
    end++;
  }
  return text.slice(0, end);
}
