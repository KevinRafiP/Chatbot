import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { addKnowledge, makeAdmin, signIn, type Account } from "./api";

export type DialogName = "masuk" | "daftar" | "pengetahuan" | "admin";

// Uses the server's message when there is one, otherwise a general message
function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.constructor === Error && error.message !== "" ? error.message : fallback;
}

// A centered box over the page; closes on Escape, the × button, or a click on the dark area
export function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onPointerDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Tutup">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

type AuthFormProps = {
  mode: "masuk" | "daftar";
  onDone: (account: Account) => void;
  onSwitch: () => void;
};

// Login or register form; the guest chats on this tab move into the account
export function AuthForm({ mode, onDone, onSwitch }: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onDone(await signIn(mode, email.trim(), password));
    } catch (err) {
      setError(errorText(err, "Tidak bisa terhubung ke server."));
      setBusy(false);
    }
  }

  return (
    <form className="modal-form" onSubmit={submit}>
      <label>
        Email
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required autoFocus />
      </label>
      <label>
        Password
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete={mode === "daftar" ? "new-password" : "current-password"}
          minLength={8}
          maxLength={72}
          required
        />
      </label>
      {error !== "" && <p className="form-error">{error}</p>}
      <button type="submit" className="primary" disabled={busy}>
        {mode === "masuk" ? "Masuk" : "Daftar"}
      </button>
      <p className="form-switch">
        {mode === "masuk" ? "Belum punya akun?" : "Sudah punya akun?"}{" "}
        <button type="button" className="link-button" onClick={onSwitch}>
          {mode === "masuk" ? "Daftar" : "Masuk"}
        </button>
      </p>
    </form>
  );
}

// Admin only: adds one entry to the internal data the chatbot searches first
export function KnowledgeForm() {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [keywords, setKeywords] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState({ text: "", failed: false });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice({ text: "", failed: false });
    try {
      await addKnowledge(title.trim(), content.trim(), keywords.trim());
      setTitle("");
      setContent("");
      setKeywords("");
      setNotice({ text: "Pengetahuan tersimpan.", failed: false });
    } catch (err) {
      setNotice({ text: errorText(err, "Gagal menyimpan pengetahuan."), failed: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="modal-form" onSubmit={submit}>
      <label>
        Judul
        <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} required autoFocus />
      </label>
      <label>
        Isi
        <textarea value={content} onChange={(event) => setContent(event.target.value)} rows={6} required />
      </label>
      <label>
        Kata kunci (boleh kosong, pisahkan dengan koma)
        <input value={keywords} onChange={(event) => setKeywords(event.target.value)} />
      </label>
      {notice.text !== "" && <p className={notice.failed ? "form-error" : "form-success"}>{notice.text}</p>}
      <button type="submit" className="primary" disabled={busy}>
        Simpan
      </button>
    </form>
  );
}

// Admin only: gives admin rights to an email that already has an account
export function AdminForm() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState({ text: "", failed: false });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice({ text: "", failed: false });
    try {
      await makeAdmin(email.trim());
      setNotice({ text: `${email.trim()} sekarang admin.`, failed: false });
      setEmail("");
    } catch (err) {
      setNotice({ text: errorText(err, "Gagal menambah admin."), failed: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="modal-form" onSubmit={submit}>
      <label>
        Email akun yang sudah terdaftar
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoFocus />
      </label>
      {notice.text !== "" && <p className={notice.failed ? "form-error" : "form-success"}>{notice.text}</p>}
      <button type="submit" className="primary" disabled={busy}>
        Jadikan admin
      </button>
    </form>
  );
}

type AccountMenuProps = {
  account: Account | null;
  open: boolean;
  onToggle: () => void;
  onChoose: (dialog: DialogName) => void;
  onLogout: () => void;
};

// The three-dot menu at the top right; admin choices only appear for admin accounts
export function AccountMenu({ account, open, onToggle, onChoose, onLogout }: AccountMenuProps) {
  const guest = account === null || account.role === "tamu";

  return (
    <div className="account-menu">
      <button className={`more ${open ? "shown" : ""}`} onClick={onToggle} aria-label="Menu akun" aria-expanded={open}>
        ⋮
      </button>
      {open && (
        <div className="dropdown" role="menu">
          <p className="account-info">
            {guest ? "Tamu: percakapan tidak disimpan" : account.email}
            {account?.role === "admin" && <span className="badge">admin</span>}
          </p>
          {guest && (
            <>
              <button role="menuitem" onClick={() => onChoose("masuk")}>
                Masuk
              </button>
              <button role="menuitem" onClick={() => onChoose("daftar")}>
                Daftar
              </button>
            </>
          )}
          {account?.role === "admin" && (
            <>
              <button role="menuitem" onClick={() => onChoose("pengetahuan")}>
                Tambah pengetahuan
              </button>
              <button role="menuitem" onClick={() => onChoose("admin")}>
                Tambah admin
              </button>
            </>
          )}
          {!guest && (
            <button role="menuitem" className="danger" onClick={onLogout}>
              Keluar
            </button>
          )}
        </div>
      )}
    </div>
  );
}
