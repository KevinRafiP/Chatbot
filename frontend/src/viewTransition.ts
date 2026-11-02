import { flushSync } from "react-dom";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

// Fades the old screen into the new one when the browser supports it; otherwise the change just happens
export function withTransition(update: () => void) {
  if (typeof document.startViewTransition !== "function" || window.matchMedia(REDUCED_MOTION_QUERY).matches) {
    update();
    return;
  }
  document.startViewTransition(() => flushSync(update));
}
