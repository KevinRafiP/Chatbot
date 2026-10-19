import { memo, useEffect, useRef, useState, type PointerEvent } from "react";
import type { Message, Source } from "./api";
import { formatTime } from "./messageText";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
const LONG_PRESS_MS = 500;
const LONG_PRESS_MOVE_PX = 10;

// Only http and https links are opened, so a reference can never run a "javascript:" address
function isWebAddress(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

// A small "V" with no top line, pointing down
function ChevronIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Two overlapping squares, the usual copy sign
export function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <rect x="9" y="9" width="11" height="11" rx="2" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M5 15V6a2 2 0 0 1 2-2h8" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

// A star: yellow when the message is starred, hollow when it is not
export function StarIcon({ filled, size = 18 }: { filled: boolean; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" className={`star-icon ${filled ? "filled" : ""}`}>
      <path
        d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Shows one reference: its title, plus a link to open it when it has a web address
function SourceItem({ source }: { source: Source }) {
  return (
    <li>
      {source.title || source.url}
      {isWebAddress(source.url) && (
        <>
          {" "}
          <a href={source.url} target="_blank" rel="noopener noreferrer">
            [Lihat Sumber]
          </a>
        </>
      )}
    </li>
  );
}

type MessageItemProps = {
  message: Message;
  animate: boolean;
  menuOpen: boolean;
  selected: boolean;
  highlighted: boolean;
  onToggleMenu: () => void;
  onCopy: () => void;
  onToggleFavorite: () => void;
  onLongPress: () => void;
  onTap: () => void;
};

// One chat message: the bubble, a small menu at its top right (shown on hover), and the time it was sent.
// On a phone the menu is replaced by a long press, like WhatsApp
export function MessageItemView(props: MessageItemProps) {
  const { message, menuOpen, selected, highlighted } = props;
  const [length, setLength] = useState(() =>
    props.animate && !window.matchMedia(REDUCED_MOTION_QUERY).matches ? 0 : message.text.length,
  );
  const typing = length < message.text.length;
  const press = useRef<{ timer: number; x: number; y: number } | null>(null);
  const pressed = useRef(false);

  // Types a new answer out bit by bit without moving the page
  useEffect(() => {
    if (!typing) {
      return;
    }
    const step = Math.max(2, Math.ceil(message.text.length / 60));
    const timer = window.setTimeout(() => {
      setLength((current) => Math.min(current + step, message.text.length));
    }, 15);
    return () => window.clearTimeout(timer);
  }, [length, typing, message.text.length]);

  // A press is only counted for a finger, and is cancelled when the finger moves to scroll
  function startPress(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType !== "touch") {
      return;
    }
    cancelPress();
    pressed.current = false;
    const timer = window.setTimeout(() => {
      press.current = null;
      pressed.current = true;
      navigator.vibrate?.(30);
      props.onLongPress();
    }, LONG_PRESS_MS);
    press.current = { timer, x: event.clientX, y: event.clientY };
  }

  function movePress(event: PointerEvent<HTMLDivElement>) {
    const start = press.current;
    if (start && Math.hypot(event.clientX - start.x, event.clientY - start.y) > LONG_PRESS_MOVE_PX) {
      cancelPress();
    }
  }

  function cancelPress() {
    if (press.current) {
      window.clearTimeout(press.current.timer);
      press.current = null;
    }
  }

  // The tap that ends a long press must not also count as a tap
  function tap() {
    if (pressed.current) {
      pressed.current = false;
      return;
    }
    props.onTap();
  }

  const classes = ["message", message.sender, menuOpen && "menu-open", selected && "selected", highlighted && "highlight"];
  return (
    <div
      id={`message-${message.id}`}
      className={classes.filter(Boolean).join(" ")}
      onPointerDown={startPress}
      onPointerMove={movePress}
      onPointerUp={cancelPress}
      onPointerCancel={cancelPress}
      onClick={tap}
      onContextMenu={(event) => {
        if (window.matchMedia("(hover: none)").matches) event.preventDefault();
      }}
    >
      {message.sender === "bot" && <span className="bot-avatar" aria-hidden="true" />}
      <div className="message-body">
        <div className="bubble-wrap">
          <div className={`bubble ${message.sender}`}>
            {message.text.slice(0, length)}
            {!typing && message.sources.length > 0 && (
              <div className="sources">
                <p className="sources-title">Sumber Referensi</p>
                <ol>
                  {message.sources.map((source, index) => (
                    <SourceItem key={index} source={source} />
                  ))}
                </ol>
              </div>
            )}
          </div>
          {!typing && (
            <div className="message-menu" onClick={(event) => event.stopPropagation()}>
              <button
                type="button"
                className="message-menu-button"
                onClick={props.onToggleMenu}
                aria-label="Menu pesan"
                aria-expanded={menuOpen}
              >
                <ChevronIcon />
              </button>
              {menuOpen && (
                <div className="dropdown message-dropdown" role="menu">
                  <button role="menuitem" onClick={props.onCopy}>
                    <CopyIcon />
                    Salin
                  </button>
                  <button role="menuitem" onClick={props.onToggleFavorite}>
                    <StarIcon filled={message.favorite} />
                    {message.favorite ? "Hapus favorit" : "Favorit"}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        <span className="message-time">
          {message.favorite && <StarIcon filled size={12} />}
          {formatTime(message.sentAt)}
        </span>
      </div>
    </div>
  );
}

// Typing in the input box no longer redraws every message: one is redrawn only when its own data changes.
// The click handlers are left out on purpose, since App makes new ones on every render
export const MessageItem = memo(
  MessageItemView,
  (before, after) =>
    before.message === after.message &&
    before.animate === after.animate &&
    before.menuOpen === after.menuOpen &&
    before.selected === after.selected &&
    before.highlighted === after.highlighted,
);

// The bubble shown while the answer is being made: the answer so far, or else the current step such as "Mencari: ..."
export function TypingItem({ status, text }: { status: string; text: string }) {
  return (
    <div className="message bot">
      <span className="bot-avatar" aria-hidden="true" />
      <div className="message-body">
        {text !== "" ? (
          <div className="bubble bot streaming">{text}</div>
        ) : (
          <div className="bubble bot typing">{status || "Mengetik"}</div>
        )}
      </div>
    </div>
  );
}
