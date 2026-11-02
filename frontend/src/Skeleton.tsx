// Gray shimmering shapes shown in place of content that is still loading, so the page does not look empty

const CHAT_ROWS = [
  { sender: "user", width: "45%" },
  { sender: "bot", width: "75%" },
  { sender: "user", width: "35%" },
  { sender: "bot", width: "60%" },
];

// A few message bubbles while a saved conversation is being opened
export function ChatSkeleton() {
  return (
    <div className="skeleton-chat" role="status" aria-label="Memuat percakapan">
      {CHAT_ROWS.map((row, index) => (
        <div key={index} className={`skeleton-row ${row.sender}`}>
          {row.sender === "bot" && <span className="skeleton skeleton-avatar" />}
          <span className="skeleton skeleton-bubble" style={{ width: row.width }} />
        </div>
      ))}
    </div>
  );
}

// List rows for the conversation list and the starred messages; each row has one bar per line
export function ListSkeleton({ rows, lines = 1 }: { rows: number; lines?: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, row) => (
        <li key={row} className="skeleton-item" aria-hidden="true">
          {Array.from({ length: lines }, (_, line) => (
            <span key={line} className="skeleton skeleton-line" style={{ width: `${90 - ((row + line) % 3) * 20}%` }} />
          ))}
        </li>
      ))}
    </>
  );
}
