import { useState, type FormEvent } from "react";

type Message = {
  id: number;
  sender: "user" | "bot";
  text: string;
};

type MessageItemProps = {
  message: Message;
};

// Shows one chat message with its sender label
function MessageItem({ message }: MessageItemProps) {
  const label = message.sender === "user" ? "Kamu" : "Bot";
  return (
    <li>
      <strong>{label}:</strong> {message.text}
    </li>
  );
}

// Main page: holds the message list and the input form
function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");

  // Adds the typed text to the list, then clears the input
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (text === "") {
      return;
    }

    const newMessage: Message = { id: Date.now(), sender: "user", text };
    setMessages([...messages, newMessage]);
    setInput("");
  }

  return (
    <div>
      <h1>Latihan Chat</h1>

      {messages.length === 0 && <p>Belum ada pesan.</p>}

      <ul>
        {messages.map((message) => (
          <MessageItem key={message.id} message={message} />
        ))}
      </ul>

      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Tulis pesan"
        />
        <button type="submit" disabled={input.trim() === ""}>
          Kirim
        </button>
      </form>

      {messages.length > 0 && (
        <button onClick={() => setMessages([])}>Hapus semua</button>
      )}
    </div>
  );
}

export default App;