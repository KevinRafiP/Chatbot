import { useEffect, useRef, useState, type PointerEvent, type RefObject } from "react";

const HANDLE_HEIGHT = 48;

type ScrollHandleProps = { target: RefObject<HTMLElement | null>; faded: boolean };

// Half-circle grip on the right edge for touch screens: drag it to scroll the chat quickly
export function ScrollHandle({ target, faded }: ScrollHandleProps) {
  const [top, setTop] = useState(0);
  const [visible, setVisible] = useState(false);
  const [tapped, setTapped] = useState(false);
  const [dragging, setDragging] = useState(false);
  const handleRef = useRef<HTMLDivElement>(null);

  // Keeps the grip in line with the scroll position, and hides it when there is nothing to scroll
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
        const room = box.scrollHeight - box.clientHeight;
        setVisible(room > 8);
        const progress = room > 0 ? box.scrollTop / room : 0;
        setTop(box.offsetTop + progress * (box.clientHeight - HANDLE_HEIGHT));
      });
    }
    // A tap on the chat fades the grip so it does not cover the messages; a swipe brings it back
    function fade(event: Event) {
      if (!handleRef.current?.contains(event.target as Node)) setTapped(true);
    }
    function show() {
      setTapped(false);
    }

    const resize = new ResizeObserver(update);
    resize.observe(box);
    const mutation = new MutationObserver(update);
    mutation.observe(box, { childList: true, subtree: true, characterData: true });
    box.addEventListener("scroll", update, { passive: true });
    box.addEventListener("pointerdown", fade);
    box.addEventListener("touchmove", show, { passive: true });
    update();
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      mutation.disconnect();
      box.removeEventListener("scroll", update);
      box.removeEventListener("pointerdown", fade);
      box.removeEventListener("touchmove", show);
    };
  }, [target]);

  // Moves the chat to the spot that matches the finger's height along the edge
  function scrollTo(event: PointerEvent<HTMLDivElement>) {
    const box = target.current;
    if (box === null) return;
    const area = box.getBoundingClientRect();
    const progress = (event.clientY - area.top - HANDLE_HEIGHT / 2) / (area.height - HANDLE_HEIGHT);
    box.scrollTo({ top: Math.min(Math.max(progress, 0), 1) * (box.scrollHeight - box.clientHeight) });
  }

  if (!visible) {
    return null;
  }

  return (
    <div
      ref={handleRef}
      className={`scroll-handle ${(faded || tapped) && !dragging ? "faded" : ""}`}
      style={{ top }}
      aria-hidden="true"
      onPointerDown={(event) => {
        event.currentTarget.setPointerCapture(event.pointerId);
        setDragging(true);
        setTapped(false);
      }}
      onPointerMove={(event) => {
        if (dragging) scrollTo(event);
      }}
      onPointerUp={() => setDragging(false)}
      onPointerCancel={() => setDragging(false)}
    />
  );
}
