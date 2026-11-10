import { memo, useEffect, useLayoutEffect, useRef, useState, type PointerEvent } from "react";
import type { Message, Rating, Source } from "./api";
import { Linkified, Markdown } from "./Markdown";
import { formatTime, hideFollowUps, looksFormatted } from "./messageText";
import { useSmoothText } from "./useSmoothText";

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

// A paperclip, the usual sign for an attached file
export function PaperclipIcon({ size = 18 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      <path
        d="M21 11.5l-8.6 8.6a5 5 0 0 1-7.1-7.1l8.6-8.6a3.5 3.5 0 0 1 5 5l-8.6 8.6a2 2 0 0 1-2.8-2.8l7.9-7.9"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
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

// A pencil, for editing a question
export function PencilIcon({ size = 18 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      <path
        d="M4 20h4L19 9l-4-4L4 16zM14 6l4 4"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// An arrow into a tray, for saving a message as a file
export function DownloadIcon({ size = 18 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      <path
        d="M12 4v11M7 10l5 5 5-5M5 19h14"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// A circular arrow, for making an answer again
function RegenerateIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
      <path
        d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// A triangle pointing right, the usual play sign, used for sending
export function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

// A square, the usual stop sign
export function StopIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
    </svg>
  );
}

// A thumb pointing up for "like", or down for "dislike"; filled when chosen
function ThumbIcon({ down, filled }: { down?: boolean; filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true" style={down ? { transform: "scaleY(-1)" } : undefined}>
      <path
        d="M7 10v10H4V10zM7 10l4-7a2 2 0 0 1 3 2l-1 5h5.5a2 2 0 0 1 2 2.4l-1.4 6A2 2 0 0 1 17.2 20H7"
        fill={filled ? "currentColor" : "none"}
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
  quiet: boolean;
  menuOpen: boolean;
  selected: boolean;
  highlighted: boolean;
  onToggleMenu: () => void;
  onCopy: () => void;
  onToggleFavorite: () => void;
  onLongPress: () => void;
  onTap: () => void;
  canRate: boolean;
  onRate: (rating: Rating) => void;
  onRetry?: () => void;
  onDownload: () => void;
  // set for a question that can be edited; editing shows a text box in place of the bubble
  onEdit?: () => void;
  editing: boolean;
  // later is true when messages after this question will be replaced by the new answer
  editReplacesLater: boolean;
  onEditDone: (text: string | null) => void;
  // set for the newest answer, which can be made again
  onRegenerate?: () => void;
  // set for the newest answer, so its follow-up questions show as buttons
  onSuggest?: (text: string) => void;
};

// The text box that replaces a question while it is edited; Ctrl+Enter sends and Escape cancels
function EditBox({ text, replacesLater, onDone }: { text: string; replacesLater: boolean; onDone: (text: string | null) => void }) {
  const [draft, setDraft] = useState(text);
  const ready = draft.trim() !== "" && draft.trim() !== text.trim();
  return (
    <div className="edit-box" onClick={(event) => event.stopPropagation()}>
      <textarea
        value={draft}
        autoFocus
        maxLength={2000}
        rows={Math.min(8, Math.max(2, draft.split("\n").length))}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") onDone(null);
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey) && ready) onDone(draft.trim());
        }}
        aria-label="Edit pertanyaan"
      />
      {replacesLater && <p className="edit-hint">Jawaban dan pesan sesudahnya akan diganti dengan jawaban baru.</p>}
      <div className="edit-actions">
        <button type="button" className="edit-cancel" onClick={() => onDone(null)}>
          Batal
        </button>
        <button type="button" className="edit-send" disabled={!ready} onClick={() => onDone(draft.trim())}>
          Kirim
        </button>
      </div>
    </div>
  );
}

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

  // A selected message is left to the phone, so holding a word selects text with the phone's own copy menu
  function startPress(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType !== "touch" || selected) {
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
    // a tap that ends selecting text keeps the message selected
    if (selected && !document.getSelection()?.isCollapsed) {
      return;
    }
    props.onTap();
  }

  const classes = [
    "message",
    message.sender,
    props.quiet && "quiet",
    menuOpen && "menu-open",
    selected && "selected",
    highlighted && "highlight",
  ];
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
        if (!selected && window.matchMedia("(hover: none)").matches) event.preventDefault();
      }}
    >
      {message.sender === "bot" && <span className="bot-avatar" aria-hidden="true" />}
      <div className="message-body">
        {props.editing ? (
          <EditBox text={message.text} replacesLater={props.editReplacesLater} onDone={props.onEditDone} />
        ) : (
          <div className="bubble-wrap">
            <div className={`bubble ${message.sender}`}>
              {message.attachment !== "" && (
                <span className="message-attachment">
                  <PaperclipIcon size={14} />
                  {message.attachment}
                </span>
              )}
              {message.sender === "bot" || looksFormatted(message.text) ? (
                <Markdown text={message.text.slice(0, length)} partial={typing} />
              ) : (
                <Linkified text={message.text.slice(0, length)} />
              )}
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
                    {props.onEdit && (
                      <button role="menuitem" onClick={props.onEdit}>
                        <PencilIcon />
                        Edit
                      </button>
                    )}
                    <button role="menuitem" onClick={props.onDownload}>
                      <DownloadIcon />
                      Unduh
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        {message.note && (
          <p className="message-note" onClick={(event) => event.stopPropagation()}>
            {message.note}
            {props.onRetry && (
              <button type="button" className="retry-button" onClick={props.onRetry}>
                Coba lagi
              </button>
            )}
          </p>
        )}
        <span className="message-time">
          {message.favorite && <StarIcon filled size={12} />}
          {formatTime(message.sentAt)}
          {props.canRate && !typing && (
            <span className="rating" onClick={(event) => event.stopPropagation()}>
              <button
                type="button"
                className={message.rating === 1 ? "chosen" : ""}
                onClick={() => props.onRate(message.rating === 1 ? 0 : 1)}
                aria-label="Jawaban bagus"
                aria-pressed={message.rating === 1}
                title="Jawaban bagus"
              >
                <ThumbIcon filled={message.rating === 1} />
              </button>
              <button
                type="button"
                className={message.rating === -1 ? "chosen" : ""}
                onClick={() => props.onRate(message.rating === -1 ? 0 : -1)}
                aria-label="Jawaban kurang bagus"
                aria-pressed={message.rating === -1}
                title="Jawaban kurang bagus"
              >
                <ThumbIcon down filled={message.rating === -1} />
              </button>
            </span>
          )}
          {props.onRegenerate && !typing && (
            <span className="rating regenerate" onClick={(event) => event.stopPropagation()}>
              <button type="button" onClick={props.onRegenerate} aria-label="Buat ulang jawaban" title="Buat ulang jawaban">
                <RegenerateIcon />
              </button>
            </span>
          )}
        </span>
        {props.onSuggest && !typing && message.suggestions !== undefined && message.suggestions.length > 0 && (
          <div className="suggestions" onClick={(event) => event.stopPropagation()}>
            {message.suggestions.map((text) => (
              <button key={text} type="button" className="suggestion" onClick={() => props.onSuggest?.(text)}>
                {text}
              </button>
            ))}
          </div>
        )}
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
    before.quiet === after.quiet &&
    before.menuOpen === after.menuOpen &&
    before.selected === after.selected &&
    before.highlighted === after.highlighted &&
    before.canRate === after.canRate &&
    before.editing === after.editing &&
    before.editReplacesLater === after.editReplacesLater &&
    (before.onRetry === undefined) === (after.onRetry === undefined) &&
    (before.onEdit === undefined) === (after.onEdit === undefined) &&
    (before.onRegenerate === undefined) === (after.onRegenerate === undefined) &&
    (before.onSuggest === undefined) === (after.onSuggest === undefined),
);

// The bubble shown while the answer is being made: the answer so far, or else the current step such as "Mencari: ..."
export function TypingItem({ status, text, onGrow }: { status: string; text: string; onGrow: () => void }) {
  const shown = hideFollowUps(useSmoothText(text));

  // runs before the frame is drawn, so following the answer down never shows a jump
  useLayoutEffect(() => {
    onGrow();
  }, [shown, status, onGrow]);

  return (
    <div className="message bot">
      <span className="bot-avatar" aria-hidden="true" />
      <div className="message-body">
        {/* one bubble for both steps, so it does not pop in again when the first words arrive */}
        <div className={`bubble bot ${shown !== "" ? "streaming" : "typing"}`}>
          {shown !== "" ? (
            <Markdown text={shown} partial />
          ) : (
            <span key={status} className="typing-status">
              {status || "Mengetik"}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
