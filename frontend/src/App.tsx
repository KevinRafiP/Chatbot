import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { AccountMenu, AdminForm, AuthForm, Dialog, KnowledgeForm, type DialogName } from "./AccountMenu";
import { FavoriteList } from "./FavoriteList";
import { CopyIcon, MessageItem, StarIcon, TypingItem } from "./MessageItem";
import { copyMessage } from "./messageText";
import { ScrollHandle } from "./ScrollHandle";
import {
  ApiError,
  BlockedError,
  createConversation,
  deleteConversation,
  getAccount,
  listConversations,
  listFavorites,
  listMessages,
  logout,
  onServerWaking,
  renameConversation,
  sendGuestMessage,
  sendMessage,
  setFavorite,
  verifyEmail,
  type Account,
  type AnswerUpdate,
  type Conversation,
  type FavoriteMessage,
  type Message,
} from "./api";

const MOBILE_QUERY = "(max-width: 768px)";

// The code from the link in the verification email, read once when the page opens and then removed from the address bar
const VERIFY_CODE = new URLSearchParams(window.location.search).get("verifikasi");
if (VERIFY_CODE !== null) {
  window.history.replaceState(null, "", window.location.pathname);
}
const TOAST_MS = 2000;
const HIGHLIGHT_MS = 4000;
const INPUT_MAX_HEIGHT = 200;

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
  const [inputFocused, setInputFocused] = useState(false);
  const [waking, setWaking] = useState(false);
  const [view, setView] = useState<"chat" | "favorites">("chat");
  const [favorites, setFavorites] = useState<FavoriteMessage[] | null>(null);
  const [favoritesError, setFavoritesError] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [live, setLive] = useState({ status: "", text: "" });
  const messagesRef = useRef<HTMLElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const jumpToRef = useRef<string | null>(null);
  const toastTimer = useRef(0);
  const highlightTimer = useRef(0);

  // Loads who is using this device, then their saved conversations; a guest has none.
  // Opening the link from the verification email logs into the new account first
  useEffect(() => {
    onServerWaking(setWaking);
    const start =
      VERIFY_CODE === null
        ? getAccount()
        : verifyEmail(VERIFY_CODE).then(
            (current) => {
              setToast("Email terverifikasi, selamat datang!");
              toastTimer.current = window.setTimeout(() => setToast(""), TOAST_MS);
              return current;
            },
            () => {
              setError("Link verifikasi salah atau sudah kedaluwarsa.");
              return getAccount();
            },
          );
    start
      .then(async (current) => {
        setAccount(current);
        if (current.role !== "tamu") {
          setConversations(await listConversations());
        }
      })
      .catch(() => setError("Tidak bisa terhubung ke server."));

    return () => onServerWaking(null);
  }, []);

  // Scrolls to the newest message when one is sent or a chat is opened, but not while an answer is being typed out
  // or a message is starred
  useEffect(() => {
    if (jumpToRef.current === null) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, loading]);

  // After a starred message is chosen, scrolls to it once it is on screen
  useEffect(() => {
    const target = jumpToRef.current;
    const element = target === null ? null : document.getElementById(`message-${target}`);
    if (element !== null) {
      jumpToRef.current = null;
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [messages.length, view]);

  // Closes the three-dot menu on a click outside it or on Escape
  useEffect(() => {
    if (menuId === null) {
      return;
    }
    function close(event: Event) {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event.target instanceof Element && event.target.closest(".item-menu, .account-menu, .message-menu")) return;
      setMenuId(null);
    }
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menuId]);

  // Grows the input with its lines, up to a limit, then it scrolls
  useEffect(() => {
    const box = inputRef.current;
    if (box === null) {
      return;
    }
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, INPUT_MAX_HEIGHT)}px`;
  }, [input]);


  // Leaves the phone's message selection on Escape
  useEffect(() => {
    if (selectedId === null) {
      return;
    }
    function clear(event: KeyboardEvent) {
      if (event.key === "Escape") setSelectedId(null);
    }
    document.addEventListener("keydown", clear);
    return () => document.removeEventListener("keydown", clear);
  }, [selectedId]);

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
    setSelectedId(null);
    setView("chat");
    setError("");
    closeSidebarOnMobile();
    try {
      setMessages(await listMessages(id));
    } catch {
      jumpToRef.current = null;
      setError("Gagal memuat percakapan.");
    }
  }

  // Starts an empty chat; it is saved when the first message is sent
  function startNew() {
    setActiveId(null);
    setMessages([]);
    setTypingId(null);
    setSelectedId(null);
    setView("chat");
    setError("");
    closeSidebarOnMobile();
  }

  // Shows a short note at the bottom of the chat that goes away by itself
  function showToast(text: string) {
    setToast(text);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), TOAST_MS);
  }

  // Copies a message from its menu or from the phone's selection bar
  async function copy(message: Message) {
    setMenuId(null);
    setSelectedId(null);
    showToast((await copyMessage(message)) ? "Pesan disalin" : "Gagal menyalin pesan");
  }

  // Stars or unstars a message right away; an account saves it on the server and undoes it if saving fails
  async function toggleFavorite(message: Message) {
    setMenuId(null);
    setSelectedId(null);
    if (message.id.startsWith("draft-")) {
      return;
    }
    const favorite = !message.favorite;
    const mark = (value: boolean) =>
      setMessages((current) => current.map((item) => (item.id === message.id ? { ...item, favorite: value } : item)));
    mark(favorite);
    if (isGuest) {
      return;
    }
    try {
      await setFavorite(message.id, favorite);
    } catch {
      mark(!favorite);
      setError("Gagal menyimpan pesan favorit.");
    }
  }

  // Shows the starred messages; a guest only has the ones in this page
  async function openFavorites() {
    setMenuId(null);
    setSelectedId(null);
    setView("favorites");
    setFavoritesError("");
    if (isGuest) {
      const starred = messages.filter((item) => item.favorite).reverse();
      setFavorites(starred.map((item) => ({ ...item, conversationId: "", conversationTitle: "" })));
      return;
    }
    setFavorites(null);
    try {
      setFavorites(await listFavorites());
    } catch {
      setFavoritesError("Gagal memuat pesan berbintang.");
    }
  }

  // Opens the conversation of a starred message, then scrolls to that message and makes it glow for a moment
  function openFavorite(item: FavoriteMessage) {
    jumpToRef.current = item.id;
    setHighlightId(item.id);
    window.clearTimeout(highlightTimer.current);
    highlightTimer.current = window.setTimeout(() => setHighlightId(null), HIGHLIGHT_MS);
    if (!isGuest && item.conversationId !== activeId) {
      openConversation(item.conversationId);
    } else {
      setView("chat");
    }
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

  // After login the guest chat is cleared and the account's saved chats are shown
  async function handleSignedIn(current: Account) {
    setAccount(current);
    setDialog(null);
    startNew();
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

  // A guest chat lives only in this page: it is sent with its history and never saved
  async function sendAsGuest(text: string, draftId: string, onUpdate: (update: AnswerUpdate) => void): Promise<Message> {
    const answer = await sendGuestMessage(text, messages, onUpdate);
    setMessages((current) => [
      ...current.map((item) => (item.id === draftId ? { ...item, id: `question-${draftId}` } : item)),
      answer,
    ]);
    return answer;
  }

  // Shows the current step, or adds the newly arrived piece of the answer
  function showUpdate(update: AnswerUpdate) {
    setLive((current) => {
      if (update.kind === "status") return { ...current, status: update.text };
      if (update.kind === "reset") return { ...current, text: "" };
      return { ...current, text: current.text + update.text };
    });
  }

  // On a computer Enter sends and Shift+Enter starts a new line; on a phone Enter always starts a new line.
  // Enter that confirms a word in a Japanese or Chinese keyboard is left alone
  function handleInputKey(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }
    if (window.matchMedia("(hover: none)").matches) {
      return;
    }
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }

  // Sends the question, waits for the answer, then shows both as saved by the server
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (text === "" || loading) {
      return;
    }

    const draftId = `draft-${Date.now()}`;
    setMessages((current) => [
      ...current,
      { id: draftId, sender: "user", text, sources: [], sentAt: new Date().toISOString(), favorite: false },
    ]);
    setInput("");
    setError("");
    setLive({ status: "", text: "" });
    setLoading(true);

    // An answer that already appeared piece by piece is not typed out again
    let streamed = false;
    const onUpdate = (update: AnswerUpdate) => {
      if (update.kind === "text") streamed = true;
      showUpdate(update);
    };

    try {
      if (isGuest) {
        const answer = await sendAsGuest(text, draftId, onUpdate);
        setTypingId(streamed ? null : answer.id);
        return;
      }

      let id = activeId;
      if (id === null) {
        const created = await createConversation();
        id = created.id;
        setActiveId(id);
        setConversations((current) => [created, ...current]);
      }

      const conversationId = id;
      const result = await sendMessage(conversationId, text, onUpdate);
      setMessages((current) => [
        ...current.filter((item) => item.id !== draftId),
        result.question,
        result.answer,
      ]);
      setTypingId(streamed ? null : result.answer.id);
      if (result.title !== "") {
        setConversations((current) =>
          current.map((item) => (item.id === conversationId ? { ...item, title: result.title } : item)),
        );
      }
    } catch (err) {
      setMessages((current) => current.filter((item) => item.id !== draftId));
      setInput(text);
      if (err instanceof ApiError && err.status === 403 && isGuest) {
        setError(err.message);
        openDialog("masuk");
      } else if (err instanceof ApiError && err.status === 429) {
        setError(err.message);
      } else if (err instanceof BlockedError) {
        setError("Pesan ditolak oleh pengaman server karena mirip perintah berbahaya (misalnya kode SQL). Ubah kalimatnya lalu coba lagi.");
      } else {
        setError("Pesan gagal terkirim. Coba lagi.");
      }
    } finally {
      setLoading(false);
    }
  }

  const isGuest = account === null || account.role === "tamu";
  const selected = messages.find((item) => item.id === selectedId) ?? null;
  const activeTitle = isGuest
    ? "Percakapan tamu"
    : (conversations.find((item) => item.id === activeId)?.title ?? "Percakapan baru");

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

        <button className="new-chat" onClick={isGuest ? () => openDialog("masuk") : startNew} disabled={loading}>
          + Percakapan baru
        </button>

        <p className="list-title">Riwayat</p>
        <ul className="conversation-list">
          {conversations.length === 0 && (
            <li className="list-empty">{isGuest ? "Masuk untuk menyimpan percakapan" : "Belum ada percakapan"}</li>
          )}
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
            Percakapan tamu tidak disimpan dan hilang saat halaman dimuat ulang.{" "}
            <button className="link-button" onClick={() => openDialog("masuk")}>
              Masuk
            </button>{" "}
            untuk menyimpan dan mengatur percakapan.
          </p>
        )}
      </aside>

      {sidebarOpen && <div className="backdrop" onClick={() => setSidebarOpen(false)} />}

      <div className="chat">
        <header className="chat-header">
          {selected !== null ? (
            <>
              <button className="icon-button" onClick={() => setSelectedId(null)} aria-label="Batal memilih">
                ✕
              </button>
              <span className="chat-title">1 dipilih</span>
              <button className="icon-button" onClick={() => copy(selected)} aria-label="Salin pesan">
                <CopyIcon />
              </button>
              <button
                className="icon-button"
                onClick={() => toggleFavorite(selected)}
                aria-label={selected.favorite ? "Hapus favorit" : "Jadikan favorit"}
              >
                <StarIcon filled={selected.favorite} />
              </button>
            </>
          ) : (
            <>
              {view === "favorites" ? (
                <button className="icon-button" onClick={() => setView("chat")} aria-label="Kembali ke percakapan">
                  ←
                </button>
              ) : (
                !sidebarOpen && (
                  <button className="icon-button" onClick={() => setSidebarOpen(true)} aria-label="Buka menu">
                    ☰
                  </button>
                )
              )}
              <span className="chat-title">{view === "favorites" ? "Pesan berbintang" : activeTitle}</span>
              <AccountMenu
                account={account}
                open={menuId === "account"}
                onToggle={() => setMenuId((current) => (current === "account" ? null : "account"))}
                onChoose={openDialog}
                onFavorites={openFavorites}
                onLogout={handleLogout}
              />
            </>
          )}
        </header>

        <main className={`chat-messages ${view === "favorites" ? "hidden" : ""}`} ref={messagesRef}>
          {messages.length === 0 && (
            <div className="empty">
              <span className="empty-logo" aria-hidden="true" />
              <p>Halo, ada yang bisa dibantu?</p>
            </div>
          )}

          {messages.map((message) => (
            <MessageItem
              key={message.id}
              message={message}
              animate={message.id === typingId}
              menuOpen={menuId === `msg:${message.id}`}
              selected={message.id === selectedId}
              highlighted={message.id === highlightId}
              onToggleMenu={() => setMenuId((current) => (current === `msg:${message.id}` ? null : `msg:${message.id}`))}
              onCopy={() => copy(message)}
              onToggleFavorite={() => toggleFavorite(message)}
              onLongPress={() => {
                setMenuId(null);
                setSelectedId(message.id);
              }}
              onTap={() => setSelectedId((current) => (current === null || current === message.id ? null : message.id))}
            />
          ))}

          {waking && <p className="notice">Menyalakan server, mohon tunggu sebentar...</p>}
          {loading && <TypingItem status={live.status} text={live.text} />}
          {error !== "" && <p className="error">{error}</p>}
          <div ref={bottomRef} />
        </main>
        {view === "favorites" && (
          <main className="chat-messages">
            <FavoriteList items={favorites} error={favoritesError} onOpen={openFavorite} />
          </main>
        )}
        <ScrollHandle target={messagesRef} faded={inputFocused} />
        {toast !== "" && (
          <div className="toast" role="status">
            {toast}
          </div>
        )}

        <form className={`chat-form ${view === "favorites" ? "hidden" : ""}`} onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
            onKeyDown={handleInputKey}
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