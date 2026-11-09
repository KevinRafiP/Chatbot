import { flushSync } from "react-dom";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

// Fades the old screen into the new one when the browser supports it; otherwise the change just happens.
// The fade runs the update a moment later, so the returned promise tells when the new screen is in place
export function withTransition(update: () => void): Promise<void> {
  if (typeof document.startViewTransition !== "function" || window.matchMedia(REDUCED_MOTION_QUERY).matches) {
    update();
    return Promise.resolve();
  }
  return document.startViewTransition(() => flushSync(update)).updateCallbackDone;
}
