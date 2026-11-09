import { useEffect, useState, type RefObject } from "react";

// further than this from the bottom shows the button
const AWAY_PX = 160;
// after this long without moving the mouse, touching, scrolling the wheel, or typing, the button turns see-through
const IDLE_MS = 2500;
const ACTIVITY_EVENTS = ["pointermove", "pointerdown", "wheel", "keydown", "touchstart"] as const;

type JumpButtonProps = {
  target: RefObject<HTMLElement | null>;
  // true when an answer finished while the user was reading higher up
  alert: boolean;
  // true while the AI writes, which makes the arrows move
  busy: boolean;
  onJump: () => void;
  onBottom: () => void;
};

// Round button above the input that scrolls the chat to the newest message.
// It shows "!" instead of the arrows when an answer finished out of view
export function JumpButton({ target, alert, busy, onJump, onBottom }: JumpButtonProps) {
  const [away, setAway] = useState(false);
  const [idle, setIdle] = useState(false);

  // Any movement makes the button solid again and starts the idle wait over
  useEffect(() => {
    let timer = window.setTimeout(() => setIdle(true), IDLE_MS);
    function wake() {
      setIdle(false);
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setIdle(true), IDLE_MS);
    }
    for (const name of ACTIVITY_EVENTS) {
      window.addEventListener(name, wake, { passive: true, capture: true });
    }
    return () => {
      window.clearTimeout(timer);
      for (const name of ACTIVITY_EVENTS) {
        window.removeEventListener(name, wake, { capture: true });
      }
    };
  }, []);

  // Watches the distance to the bottom while scrolling, and while messages grow or arrive
  useEffect(() => {
    const box = target.current;
    if (box === null) {
      return;
    }
    let frame = 0;
    function update() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (box === null) return;
        const far = box.scrollHeight - box.scrollTop - box.clientHeight > AWAY_PX;
        setAway(far);
        if (!far) onBottom();
      });
    }
    const resize = new ResizeObserver(update);
    resize.observe(box);
    const mutation = new MutationObserver(update);
    mutation.observe(box, { childList: true, subtree: true, characterData: true });
    box.addEventListener("scroll", update, { passive: true });
    update();
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      mutation.disconnect();
      box.removeEventListener("scroll", update);
    };
  }, [target, onBottom]);

  if (!away) {
    return null;
  }

  return (
    <div className="jump-anchor">
      <button
        type="button"
        className={`jump-button ${alert ? "alert" : busy ? "busy" : ""} ${idle ? "idle" : ""}`}
        onClick={onJump}
        aria-label={alert ? "Jawaban selesai, gulir ke bawah" : "Gulir ke bawah"}
        title={alert ? "Jawaban selesai" : "Gulir ke bawah"}
      >
        {alert ? (
          <span className="jump-alert">!</span>
        ) : (
          <span className="jump-arrows" aria-hidden="true">
            <span className="jump-chevron top" />
            <span className="jump-chevron bottom" />
          </span>
        )}
      </button>
    </div>
  );
}
