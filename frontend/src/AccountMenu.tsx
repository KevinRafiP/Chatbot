import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  addKnowledge,
  ApiError,
  getGoogleEnabled,
  getInstructions,
  makeAdmin,
  requestPasswordReset,
  resendVerification,
  resetPassword,
  saveInstructions,
  signIn,
  startGoogleSignIn,
  type Account,
} from "./api";

export type DialogName = "masuk" | "daftar" | "lupa" | "atur-ulang" | "pengetahuan" | "admin" | "kinerja" | "instruksi";

// asked once per page; the Google button only shows when the backend has Google sign-in set up
let googleEnabled: Promise<boolean> | null = null;

// How long the resend button waits; the backend also ignores a resend within one minute
const RESEND_WAIT_SECONDS = 60;
// The backend sends at most one password reset email every two minutes
const RESET_WAIT_SECONDS = 120;

// Uses the server's message when there is one, otherwise a general message
function errorText(error: unknown, fallback: string): string {
  const fromServer = error instanceof ApiError || (error instanceof Error && error.constructor === Error);
  return fromServer && error.message !== "" ? error.message : fallback;
}

type DialogProps = { title: string; onClose: () => void; children: ReactNode; wide?: boolean };

// A centered box over the page; closes on Escape, the × button, or a click on the dark area.
// wide is for content with tables, such as the performance report
export function Dialog({ title, onClose, children, wide = false }: DialogProps) {
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onPointerDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
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
  onForgot: () => void;
};

// Login or register form; the guest chats on this tab move into the account.
// A new account has to open the link sent to its email first, so the form then shows where the link went
export function AuthForm({ mode, onDone, onSwitch, onForgot }: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [remember, setRemember] = useState(true);
  const [pendingEmail, setPendingEmail] = useState("");
  const [notice, setNotice] = useState("");
  const [wait, setWait] = useState(0);
  const [google, setGoogle] = useState(false);

  useEffect(() => {
    let active = true;
    googleEnabled ??= getGoogleEnabled();
    void googleEnabled.then((enabled) => active && setGoogle(enabled));
    return () => {
      active = false;
    };
  }, []);

  // The page leaves for Google's sign-in page and comes back logged in
  async function signInWithGoogle() {
    setBusy(true);
    setError("");
    try {
      await startGoogleSignIn(remember);
    } catch (err) {
      setError(errorText(err, "Masuk dengan Google sedang tidak bisa dipakai."));
      setBusy(false);
    }
  }

  // Counts the resend wait down once per second
  useEffect(() => {
    if (wait <= 0) {
      return;
    }
    const timer = window.setTimeout(() => setWait(wait - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const account = await signIn(mode, email.trim(), password, remember);
      if (account !== null) {
        onDone(account);
        return;
      }
      setPendingEmail(email.trim());
      setWait(RESEND_WAIT_SECONDS);
    } catch (err) {
      // 403 means the password is right but the email is not confirmed yet
      if (err instanceof ApiError && err.status === 403) {
        setPendingEmail(email.trim());
      } else {
        setError(errorText(err, "Tidak bisa terhubung ke server."));
      }
    }
    setBusy(false);
  }

  async function resend() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await resendVerification(pendingEmail, remember);
      setNotice("Link baru sudah dikirim.");
      setWait(RESEND_WAIT_SECONDS);
    } catch (err) {
      setError(errorText(err, "Tidak bisa terhubung ke server."));
    }
    setBusy(false);
  }

  if (pendingEmail !== "") {
    return (
      <div className="modal-form">
        <p className="form-note">
          Buka link verifikasi yang kami kirim ke <strong>{pendingEmail}</strong> untuk mengaktifkan akun. Tidak ada di
          kotak masuk? Cek folder Spam.
        </p>
        {notice !== "" && <p className="form-success">{notice}</p>}
        {error !== "" && <p className="form-error">{error}</p>}
        <button type="button" className="primary" onClick={resend} disabled={busy || wait > 0}>
          {wait > 0 ? `Kirim ulang (${wait})` : "Kirim ulang"}
        </button>
        <p className="form-switch">
          <button type="button" className="link-button" onClick={() => setPendingEmail("")}>
            Kembali
          </button>
        </p>
      </div>
    );
  }

  return (
    <form className="modal-form" onSubmit={submit}>
      {google && (
        <>
          <button type="button" className="google-button" onClick={signInWithGoogle} disabled={busy}>
            <GoogleIcon />
            {mode === "masuk" ? "Masuk dengan Google" : "Daftar dengan Google"}
          </button>
          <p className="or-line">
            <span>atau dengan email</span>
          </p>
        </>
      )}
      <label>
        Email
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required autoFocus />
      </label>
      <label>
        Password
        <input
          type={showPassword ? "text" : "password"}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete={mode === "daftar" ? "new-password" : "current-password"}
          minLength={8}
          maxLength={72}
          required
        />
      </label>
      {mode === "masuk" && (
        <button type="button" className="link-button forgot-link" onClick={onForgot}>
          Lupa password?
        </button>
      )}
      <label className="checkbox-row">
        <input type="checkbox" checked={showPassword} onChange={(event) => setShowPassword(event.target.checked)} />
        Tampilkan password
      </label>
      <label className="checkbox-row">
        <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
        Ingat saya
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

function GoogleIcon() {
  return (
    <svg viewBox="0 0 48 48" width="18" height="18" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

// Counts down once per second; used to space out repeated emails
function useCountdown(): [number, (seconds: number) => void] {
  const [left, setLeft] = useState(0);
  useEffect(() => {
    if (left <= 0) {
      return;
    }
    const timer = window.setTimeout(() => setLeft(left - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [left]);
  return [left, setLeft];
}

// Sends a link for choosing a new password. The same message shows whether or not the email has an account,
// so nobody can use this form to find out which emails are registered
export function ForgotForm({ onBack }: { onBack: () => void }) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [wait, setWait] = useCountdown();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await requestPasswordReset(email.trim());
      setSent(true);
      setWait(RESET_WAIT_SECONDS);
    } catch (err) {
      setError(errorText(err, "Tidak bisa terhubung ke server."));
    }
    setBusy(false);
  }

  return (
    <form className="modal-form" onSubmit={submit}>
      {sent ? (
        <p className="form-note">
          Jika <strong>{email.trim()}</strong> terdaftar, link untuk membuat password baru sudah dikirim. Link berlaku 1 jam.
          Tidak ada di kotak masuk? Cek folder Spam.
        </p>
      ) : (
        <>
          <p className="form-note">Masukkan email akunmu. Kami akan mengirim link untuk membuat password baru.</p>
          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required autoFocus />
          </label>
        </>
      )}
      {error !== "" && <p className="form-error">{error}</p>}
      <button type="submit" className="primary" disabled={busy || wait > 0}>
        {!sent ? "Kirim link" : wait > 0 ? `Kirim ulang (${wait})` : "Kirim ulang"}
      </button>
      <p className="form-switch">
        <button type="button" className="link-button" onClick={onBack}>
          Kembali ke Masuk
        </button>
      </p>
    </form>
  );
}

type ResetFormProps = {
  code: string;
  onDone: (account: Account) => void;
  onRequestNew: () => void;
};

// Chooses a new password with the code from the reset email; afterwards only this device stays logged in
export function ResetForm({ code, onDone, onRequestNew }: ResetFormProps) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Password dan ulangannya tidak sama.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      onDone(await resetPassword(code, password, remember));
      return;
    } catch (err) {
      setError(errorText(err, "Tidak bisa terhubung ke server."));
    }
    setBusy(false);
  }

  return (
    <form className="modal-form" onSubmit={submit}>
      <p className="form-note">Buat password baru. Setelah disimpan, akun ini keluar dari perangkat lain.</p>
      <label>
        Password baru
        <input
          type={showPassword ? "text" : "password"}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="new-password"
          minLength={8}
          maxLength={72}
          required
          autoFocus
        />
      </label>
      <label>
        Ulangi password baru
        <input
          type={showPassword ? "text" : "password"}
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          autoComplete="new-password"
          minLength={8}
          maxLength={72}
          required  
        />
      </label>
      <label className="checkbox-row">
        <input type="checkbox" checked={showPassword} onChange={(event) => setShowPassword(event.target.checked)} />
        Tampilkan password
      </label>
      <label className="checkbox-row">
        <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
        Ingat saya
      </label>
      {error !== "" && <p className="form-error">{error}</p>}
      <button type="submit" className="primary" disabled={busy}>
        Simpan password
      </button>
      <p className="form-switch">
        Link tidak berlaku?{" "}
        <button type="button" className="link-button" onClick={onRequestNew}>
          Minta link baru
        </button>
      </p>
    </form>
  );
}

// The account's own instructions, sent with every question: a name to be called, a language, an answer style.
// They cannot override the safety rules; the agent puts them after the rules with that note
export function InstructionsForm({ onSaved }: { onSaved: () => void }) {
  const [text, setText] = useState("");
  const [limit, setLimit] = useState(1500);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // the backend counts letters, not UTF-16 units, so an emoji counts as one
  const length = [...text.trim()].length;

  useEffect(() => {
    let active = true;
    getInstructions()
      .then((data) => {
        if (!active) return;
        setText(data.text);
        setLimit(data.limit);
        setLoaded(true);
      })
      .catch((err) => active && setError(errorText(err, "Gagal memuat instruksi.")));
    return () => {
      active = false;
    };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setText(await saveInstructions(text));
      onSaved();
    } catch (err) {
      setError(errorText(err, "Gagal menyimpan instruksi."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="modal-form" onSubmit={submit}>
      <p className="form-note">
        Tulis cara AI menjawabmu, misalnya nama panggilan, bahasa, atau gaya jawaban. Berlaku untuk semua percakapan akun ini.
      </p>
      <label>
        Instruksi
        <textarea
          className="instructions-input"
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={7}
          placeholder={"Contoh: Panggil saya Kak Kevin. Jawab singkat dan pakai contoh kode Go."}
          disabled={!loaded}
          autoFocus
        />
      </label>
      <p className={`char-count ${length > limit ? "over" : ""}`} aria-live="polite">
        {length}/{limit}
      </p>
      {error !== "" && <p className="form-error">{error}</p>}
      <button type="submit" className="primary" disabled={busy || !loaded || length > limit}>
        Simpan
      </button>
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
  onFavorites: () => void;
  onLogout: () => void;
};

// The three-dot menu at the top right; admin choices only appear for admin accounts
export function AccountMenu({ account, open, onToggle, onChoose, onFavorites, onLogout }: AccountMenuProps) {
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
          <button role="menuitem" onClick={onFavorites}>
            Pesan berbintang
          </button>
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
              <button role="menuitem" onClick={() => onChoose("kinerja")}>
                Kinerja jawaban
              </button>

            </>
          )}
          {!guest && (
            <>
              <button role="menuitem" onClick={() => onChoose("instruksi")}>
                Instruksi pribadi
              </button>
              <button role="menuitem" className="danger" onClick={onLogout}>
                Keluar
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
