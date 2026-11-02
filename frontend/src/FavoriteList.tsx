import type { FavoriteMessage } from "./api";
import { StarIcon } from "./MessageItem";
import { plainMarkdown } from "./markdownPlain";
import { formatTime } from "./messageText";
import { ListSkeleton } from "./Skeleton";

type FavoriteListProps = {
  items: FavoriteMessage[] | null;
  error: string;
  onOpen: (item: FavoriteMessage) => void;
};

// The list of starred messages; choosing one jumps to it inside its conversation
export function FavoriteList({ items, error, onOpen }: FavoriteListProps) {
  if (error !== "") {
    return <p className="error">{error}</p>;
  }
  if (items === null) {
    return (
      <ul className="favorite-list" aria-busy="true" aria-label="Memuat pesan berbintang">
        <ListSkeleton rows={5} lines={2} />
      </ul>
    );
  }
  if (items.length === 0) {
    return (
      <div className="empty">
        <StarIcon filled={false} size={40} />
        <p>Belum ada pesan berbintang</p>
      </div>
    );
  }
  return (
    <ul className="favorite-list">
      {items.map((item) => (
        <li key={item.id}>
          <button type="button" onClick={() => onOpen(item)}>
            <span className="favorite-meta">
              <span className="favorite-from">
                {item.sender === "user" ? "Anda" : "Vokapas"}
                {item.conversationTitle !== "" && <> · {item.conversationTitle}</>}
              </span>
              <span className="favorite-time">{formatTime(item.sentAt)}</span>
            </span>
            <span className="favorite-text">{plainMarkdown(item.text)}</span>
            <span className="favorite-star">
              <StarIcon filled size={12} />
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
