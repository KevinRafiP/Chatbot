import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  createConversation,
  deleteConversation,
  listConversations,
  listMessages,
  logout,
  sendMessage,
  type Conversation,
  type Message,
} from "./api";

// Shows one source as a link when it is a web address, otherwise as plain text
function Source({ value }: { value: string }) {
  if (value.startsWith("http://") || value.startsWith("https://")) {
    return (
      <a href={value} target="_blank" rel="noopener noreferrer">
        {value}
      </a>
    );
  }
  return <span>{value}</span>;
}

// Shows one chat bubble with its sources, placed left or right by its sender
function MessageBubble({ message }: { message: Message }) {
  return (
    <div className={`bubble ${message.sender}`}>
      {message.text}
      {message.sources.length > 0 && (
        <ul className="sources">
          {message.sources.map((source) => (
            <li key={source}>
              <Source value={source} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Chat page: conversation list on the left, messages and input form on the right
function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  // Loads the conversation list once when the page opens
  useEffect(() => {
    listConversations()
      .then(setConversations)
      .catch(() => setError("Tidak bisa terhubung ke server."));
  }, []);

  // Scrolls to the newest message whenever the list changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Opens a saved conversation and loads its messages
  async function openConversation(id: number) {
    setActiveId(id);
    setMessages([]);
    setError("");
    try {
      setMessages(await listMessages(id));
    } catch {
      setError("Gagal memuat percakapan.");
    }
  }

  // Starts an empty chat; it is saved when the first message is sent
  function startNew() {
    setActiveId(null);
    setMessages([]);
    setError("");
  }

  // Deletes a conversation after the user confirms
  async function removeConversation(id: number) {
    if (!window.confirm("Hapus percakapan ini?")) {
      return;
    }
    try {
      await deleteConversation(id);
      setConversations((current) => current.filter((item) => item.id !== id));
      if (id === activeId) {
        startNew();
      }
    } catch {
      setError("Gagal menghapus percakapan.");
    }
  }

    // Deletes this device's login session; the next action starts as a new guest
  async function endSession() {
    if (!window.confirm("Hapus sesi di perangkat ini? Semua percakapan tidak bisa dibuka lagi.")) {
      return;
    }
    try {
      await logout();
      setConversations([]);
      startNew();
    } catch {
      setError("Gagal menghapus sesi.");
    }
  }

  // Sends the question, waits for the answer, then shows both as saved by the server
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (text === "" || loading) {
      return;
    }

    const draftId = -Date.now();
    setMessages((current) => [...current, { id: draftId, sender: "user", text, sources: [] }]);
    setInput("");
    setError("");
    setLoading(true);

    try {
      let id = activeId;
      if (id === null) {
        const created = await createConversation();
        id = created.id;
        setActiveId(id);
        setConversations((current) => [created, ...current]);
      }

      const conversationId = id;
      const result = await sendMessage(conversationId, text);
      setMessages((current) => [
        ...current.filter((item) => item.id !== draftId),
        result.question,
        result.answer,
      ]);
      if (result.title !== "") {
        setConversations((current) =>
          current.map((item) => (item.id === conversationId ? { ...item, title: result.title } : item)),
        );
      }
    } catch {
      setError("Pesan gagal terkirim. Coba lagi.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <button className="new-chat" onClick={startNew} disabled={loading}>
          + Percakapan baru
        </button>

        <ul className="conversation-list">
          {conversations.map((item) => (
            <li key={item.id} className={item.id === activeId ? "active" : ""}>
              <button className="open" onClick={() => openConversation(item.id)} disabled={loading}>
                {item.title}
              </button>
              <button
                className="delete"
                onClick={() => removeConversation(item.id)}
                disabled={loading}
                aria-label="Hapus percakapan"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        <button className="end-session" onClick={endSession} disabled={loading}>
          Hapus sesi
        </button>
      </aside>

      <div className="chat">
        <header className="chat-header">Chatbot</header>

        <main className="chat-messages">
          {messages.length === 0 && <p className="empty">Halo, ada yang bisa dibantu?</p>}

          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {loading && <div className="bubble bot typing">Mengetik...</div>}
          {error !== "" && <p className="error">{error}</p>}
          <div ref={bottomRef} />
        </main>

        <form className="chat-form" onSubmit={handleSubmit}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Tulis pertanyaan..."
            maxLength={2000}
          />
          <button type="submit" disabled={input.trim() === "" || loading}>
            Kirim
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;