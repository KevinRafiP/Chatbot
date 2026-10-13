import { useEffect, useRef, useState, type FormEvent } from "react";
import { AccountMenu, AdminForm, AuthForm, Dialog, KnowledgeForm, type DialogName } from "./AccountMenu";
import {
  createConversation,
  deleteConversation,
  getAccount,
  listConversations,
  listMessages,
  logout,
  renameConversation,
  sendMessage,
  type Account,
  type Conversation,
  type Message,
  type Source,
} from "./api";

const MOBILE_QUERY = "(max-width: 768px)";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

// Shows one reference: its title, plus a link to open it when it has a web address
function SourceItem({ source }: { source: Source }) {
  return (
    <li>
      {source.title || source.url}
      {source.url !== "" && (
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

type MessageBubbleProps = { message: Message; animate: boolean; onGrow: () => void };

// Shows one chat bubble; a new answer is typed out bit by bit, then its references appear
function MessageBubble({ message, animate, onGrow }: MessageBubbleProps) {
  const [length, setLength] = useState(() =>
    animate && !window.matchMedia(REDUCED_MOTION_QUERY).matches ? 0 : message.text.length,
  );
  const typing = length < message.text.length;

  useEffect(() => {
    if (!typing) {
      return;
    }
    const step = Math.max(2, Math.ceil(message.text.length / 150));
    const timer = window.setTimeout(() => {
      setLength((current) => Math.min(current + step, message.text.length));
      onGrow();
    }, 15);
    return () => window.clearTimeout(timer);
  }, [length, typing, message.text.length, onGrow]);
  return (
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
  );
}

type ConversationItemProps = {
  conversation: Conversation;
  active: boolean;
  menuOpen: boolean;
  disabled: boolean;
  onOpen: () => void;
  onToggleMenu: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
};

// One row in the sidebar: the title opens the chat, the three-dot button opens rename and delete
function ConversationItem(props: ConversationItemProps) {
  const { conversation, active, menuOpen, disabled } = props;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(conversation.title);

  function startRename() {
    setDraft(conversation.title);
    setEditing(true);
    props.onToggleMenu();
  }

  function finishRename() {
    setEditing(false);
    const title = draft.trim();
    if (title !== "" && title !== conversation.title) {
      props.onRename(title);
    }
  }

  if (editing) {
    return (
      <li className="active">
        <input
          className="rename"
          value={draft}
          autoFocus
          maxLength={100}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={finishRename}
          onKeyDown={(event) => {
            if (event.key === "Enter") finishRename();
            if (event.key === "Escape") setEditing(false);
          }}
        />
      </li>
    );
  }

  return (
    <li className={active ? "active" : ""}>
      <button className="open" onClick={props.onOpen} disabled={disabled} title={conversation.title}>
        {conversation.title}
      </button>
      <div className="item-menu">
        <button
          className={`more ${menuOpen ? "shown" : ""}`}
          onClick={props.onToggleMenu}
          disabled={disabled}
          aria-label="Menu percakapan"
          aria-expanded={menuOpen}
        >
          ⋮
        </button>
        {menuOpen && (
          <div className="dropdown" role="menu">
            <button role="menuitem" onClick={startRename}>
              Ganti nama
            </button>
            <button role="menuitem" className="danger" onClick={props.onDelete}>
              Hapus
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

// Chat page: collapsible conversation list on the left, messages and input form on the right
function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(() => !window.matchMedia(MOBILE_QUERY).matches);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [account, setAccount] = useState<Account | null>(null);
  const [dialog, setDialog] = useState<DialogName | null>(null);
  const [typingId, setTypingId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Loads who is using this device, then their conversations, once when the page opens
  useEffect(() => {
    getAccount()
      .then((current) => {
        setAccount(current);
        return listConversations();
      })
      .then(setConversations)
      .catch(() => setError("Tidak bisa terhubung ke server."));
  }, []);

  // Scrolls to the newest message whenever the list changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Closes the three-dot menu on a click outside it or on Escape
  useEffect(() => {
    if (menuId === null) {
      return;
    }
    function close(event: Event) {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event.target instanceof Element && event.target.closest(".item-menu, .account-menu")) return;
      setMenuId(null);
    }
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menuId]);

  // On a phone the list covers the chat, so it closes after a choice
  function closeSidebarOnMobile() {
    if (window.matchMedia(MOBILE_QUERY).matches) {
      setSidebarOpen(false);
    }
  }

  // Opens a saved conversation and loads its messages
  async function openConversation(id: string) {
    setActiveId(id);
    setMessages([]);
    setTypingId(null);
    setError("");
    closeSidebarOnMobile();
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
    setTypingId(null);
    setError("");
    closeSidebarOnMobile();
  }

  // Saves a new title, then shows the title the server kept
  async function changeTitle(id: string, title: string) {
    try {
      const saved = await renameConversation(id, title);
      setConversations((current) => current.map((item) => (item.id === id ? { ...item, title: saved.title } : item)));
    } catch {
      setError("Gagal mengganti nama percakapan.");
    }
  }

  // Deletes a conversation after the user confirms
  async function removeConversation(id: string) {
    setMenuId(null);
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

  // Opens a form from the account menu
  function openDialog(name: DialogName) {
    setMenuId(null);
    setDialog(name);
  }

  // After login the list also holds the chats this tab made as a guest
  async function handleSignedIn(current: Account) {
    setAccount(current);
    setDialog(null);
    try {
      setConversations(await listConversations());
    } catch {
      setError("Gagal memuat percakapan.");
    }
  }

  // Logs out of the account; the page continues as a new guest
  async function handleLogout() {
    setMenuId(null);
    try {
      await logout();
      setConversations([]);
      startNew();
      setAccount(await getAccount());
    } catch {
      setError("Gagal keluar dari akun.");
    }
  }

  // Sends the question, waits for the answer, then shows both as saved by the server
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (text === "" || loading) {
      return;
    }

    const draftId = `draft-${Date.now()}`;
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
      setTypingId(result.answer.id);
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

  const activeTitle = conversations.find((item) => item.id === activeId)?.title ?? "Percakapan baru";
  const isGuest = account === null || account.role === "tamu";

  return (
    <div className={`app ${sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
      <aside className="sidebar" aria-hidden={!sidebarOpen}>
        <div className="sidebar-header">
          <span className="brand">
            <span className="brand-logo" aria-hidden="true" />
            Vokapas
          </span>
          <button className="icon-button" onClick={() => setSidebarOpen(false)} aria-label="Tutup menu">
            «
          </button>
        </div>

        <button className="new-chat" onClick={startNew} disabled={loading}>
          + Percakapan baru
        </button>

        <p className="list-title">Riwayat</p>
        <ul className="conversation-list">
          {conversations.length === 0 && <li className="list-empty">Belum ada percakapan</li>}
          {conversations.map((item) => (
            <ConversationItem
              key={item.id}
              conversation={item}
              active={item.id === activeId}
              menuOpen={item.id === menuId}
              disabled={loading}
              onOpen={() => openConversation(item.id)}
              onToggleMenu={() => setMenuId((current) => (current === item.id ? null : item.id))}
              onRename={(title) => changeTitle(item.id, title)}
              onDelete={() => removeConversation(item.id)}
            />
          ))}
        </ul>

        {isGuest && (
          <p className="guest-note">
            Percakapan tamu hilang saat tab ditutup.{" "}
            <button className="link-button" onClick={() => openDialog("masuk")}>
              Masuk
            </button>{" "}
            untuk menyimpannya.
          </p>
        )}
      </aside>

      {sidebarOpen && <div className="backdrop" onClick={() => setSidebarOpen(false)} />}

      <div className="chat">
        <header className="chat-header">
          {!sidebarOpen && (
            <button className="icon-button" onClick={() => setSidebarOpen(true)} aria-label="Buka menu">
              ☰
            </button>
          )}
          <span className="chat-title">{activeTitle}</span>
          <AccountMenu
            account={account}
            open={menuId === "account"}
            onToggle={() => setMenuId((current) => (current === "account" ? null : "account"))}
            onChoose={openDialog}
            onLogout={handleLogout}
          />
        </header>

        <main className="chat-messages">
          {messages.length === 0 && (
            <div className="empty">
              <span className="empty-logo" aria-hidden="true" />
              <p>Halo, ada yang bisa dibantu?</p>
            </div>
          )}

          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              animate={message.id === typingId}
              onGrow={() => bottomRef.current?.scrollIntoView({ block: "end" })}
            />
          ))}

          {loading && <div className="bubble bot typing">Mengetik</div>}
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
      {(dialog === "masuk" || dialog === "daftar") && (
        <Dialog title={dialog === "masuk" ? "Masuk" : "Daftar"} onClose={() => setDialog(null)}>
          <AuthForm
            key={dialog}
            mode={dialog}
            onDone={handleSignedIn}
            onSwitch={() => setDialog(dialog === "masuk" ? "daftar" : "masuk")}
          />
        </Dialog>
      )}
      {dialog === "pengetahuan" && account?.role === "admin" && (
        <Dialog title="Tambah pengetahuan" onClose={() => setDialog(null)}>
          <KnowledgeForm />
        </Dialog>
      )}
      {dialog === "admin" && account?.role === "admin" && (
        <Dialog title="Tambah admin" onClose={() => setDialog(null)}>
          <AdminForm />
        </Dialog>
      )}
    </div>
  );
}

export default App;