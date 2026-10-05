import { useEffect, useRef, useState, type FormEvent } from "react";
import { askBot } from "./api";

type Message = {
  id: number;
  sender: "user" | "bot";
  text: string;
};

// Shows one chat bubble, placed left or right by its sender
function MessageBubble({ message }: { message: Message }) {
  return <div className={`bubble ${message.sender}`}>{message.text}</div>;
}

// Chat page: header, message list, and input form
function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scrolls to the newest message whenever the list changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Appends one message to the end of the list
  function addMessage(sender: Message["sender"], text: string) {
    setMessages((current) => [...current, { id: current.length + 1, sender, text }]);
  }

  // Sends the question, waits for the answer, then shows it
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (text === "" || loading) {
      return;
    }

    addMessage("user", text);
    setInput("");
    setLoading(true);

    try {
      const answer = await askBot(text);
      addMessage("bot", answer);
    } catch {
      addMessage("bot", "Maaf, terjadi kesalahan. Coba lagi.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat">
      <header className="chat-header">Chatbot</header>

      <main className="chat-messages">
        {messages.length === 0 && <p className="empty">Halo, ada yang bisa dibantu?</p>}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {loading && <div className="bubble bot typing">Mengetik...</div>}
        <div ref={bottomRef} />
      </main>

      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Tulis pertanyaan..."
        />
        <button type="submit" disabled={input.trim() === "" || loading}>
          Kirim
        </button>
      </form>
    </div>
  );
}

export default App;