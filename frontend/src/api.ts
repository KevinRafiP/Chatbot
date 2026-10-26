const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8080").replace(/\/$/, "");
const ACCOUNT_TOKEN_KEY = "chatbot_token";
const GUEST_TOKEN_KEY = "chatbot_guest_token";

export type Conversation = { id: string; title: string };
export type Source = { title: string; url: string };
export type Message = {
  id: string;
  sender: "user" | "bot";
  text: string;
  sources: Source[];
  sentAt: string;
  favorite: boolean;
  attachment: string;
};
// Text read from an uploaded file; it is sent along with the next question
export type Attachment = { name: string; text: string; truncated: boolean; pages: number | null };
export type FavoriteMessage = Message & { conversationId: string; conversationTitle: string };
export type SendResult = { title: string; question: Message; answer: Message };
export type Role = "tamu" | "user" | "admin";
export type Account = { id: string; name: string; email: string; role: Role };

// What the backend reports while an answer is being made: a step such as "Mencari: ...", a new piece of the
// answer, or "reset" when the text so far was only a lead-in before a search and has to be cleared
export type AnswerUpdate = { kind: "status"; text: string } | { kind: "text"; text: string } | { kind: "reset" };
// "fast" answers quickly with fewer searches, "deep" thinks longer and may read more sources
export type AnswerMode = "fast" | "deep";

type ApiResponse<T> = { status: string; message: string; data: T };
type RawConversation = { id: string; judul: string };
type RawSource = { judul: string; url: string };
type RawMessage = {
  id: string;
  pengirim: "user" | "asisten";
  isi: string;
  sumber: RawSource[] | null;
  favorit: boolean;
  lampiran?: string;
  dibuat_pada: string;
};
type RawFavorite = RawMessage & { percakapan_id: string; judul_percakapan: string };
type RawSendResult = { judul: string; pesan: RawMessage; jawaban: RawMessage };
type RawAccount = { id: string; nama: string; jenis: Role; email?: string };
type RawSession = { token: string; pengguna: RawAccount };
type RawSignIn = RawSession | { perlu_verifikasi: true; email: string };
type RawAnswer = { jawaban: string; sumber: RawSource[] | null };
type RawFile = { nama: string; teks: string; terpotong: boolean; halaman: number | null };

// Render free puts the backend to sleep; these are the waits before each new try while it wakes up (about 2.5 minutes in total)
const RETRY_DELAYS_MS = [5000, 10000, 15000, 20000, 30000, 30000, 40000];

// Error with the HTTP status, so the UI can tell a guest limit or rate limit from other failures
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Thrown when the request was refused before reaching the backend, usually because its text looks like an attack
export class BlockedError extends Error {}

let token =
  readToken(sessionStorage, ACCOUNT_TOKEN_KEY) ?? readToken(localStorage, ACCOUNT_TOKEN_KEY) ?? readToken(localStorage, GUEST_TOKEN_KEY);
let loginPromise: Promise<string> | null = null;
let wakingListener: ((waking: boolean) => void) | null = null;

// Reads a saved token; storage can be blocked by the browser
function readToken(storage: Storage, key: string): string | null {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

// An account token goes to localStorage when "Ingat saya" is ticked, otherwise to sessionStorage, which the browser
// empties when the tab is closed. The guest token always lives in localStorage, so closing the tab does not reset the
// guest message limit. Every save clears the old tokens first, so logging out also forgets the remembered login
function saveToken(value: string | null, kind: "account" | "guest" = "account", remember = true) {
  token = value;
  try {
    localStorage.removeItem(ACCOUNT_TOKEN_KEY);
    localStorage.removeItem(GUEST_TOKEN_KEY);
    sessionStorage.removeItem(ACCOUNT_TOKEN_KEY);
    if (value !== null) {
      const storage = kind === "account" && !remember ? sessionStorage : localStorage;
      storage.setItem(kind === "account" ? ACCOUNT_TOKEN_KEY : GUEST_TOKEN_KEY, value);
    }
  } catch {
    // storage is blocked, the token then only lives in memory
  }
}

// A failed request while the health check still answers means the server is awake and something in front of it,
// such as Render's firewall, refused this one request
async function serverAnswers(): Promise<boolean> {
  try {
    return (await fetch(`${API_URL}/kesehatan`)).ok;
  } catch {
    return false;
  }
}

// Lets the UI show a notice while the backend is waking up
export function onServerWaking(listener: ((waking: boolean) => void) | null) {
  wakingListener = listener;
}

// A sleeping backend makes fetch fail or answer 502/503/504, so wait and try again a few times
async function fetchWithRetry(url: string, init?: RequestInit): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    const lastTry = attempt >= RETRY_DELAYS_MS.length;
    try {
      const response = await fetch(url, init);
      if (lastTry || ![502, 503, 504].includes(response.status)) {
        wakingListener?.(false);
        return response;
      }
    } catch (error) {
      if (await serverAnswers()) {
        wakingListener?.(false);
        throw new BlockedError();
      }
      if (lastTry) {
        wakingListener?.(false);
        throw error;
      }
    }
    wakingListener?.(true);
    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[attempt]));
  }
}

// Asks the backend for a new guest session
async function loginGuest(): Promise<string> {
  const response = await fetchWithRetry(`${API_URL}/sesi/tamu`, { method: "POST" });
  if (!response.ok) {
    throw new Error("Gagal masuk sebagai tamu");
  }
  const body: ApiResponse<{ token: string }> = await response.json();
  saveToken(body.data.token, "guest");
  return body.data.token;
}

// Returns the saved token, or logs in as guest once when there is none
function ensureToken(): Promise<string> {
  if (token !== null) {
    return Promise.resolve(token);
  }
  if (loginPromise === null) {
    loginPromise = loginGuest().finally(() => {
      loginPromise = null;
    });
  }
  return loginPromise;
}

// Calls one backend endpoint with the saved token and returns its data
async function request<T>(method: string, path: string, body?: unknown, retry = true): Promise<T> {
  const currentToken = await ensureToken();
  const headers: Record<string, string> = { Authorization: `Bearer ${currentToken}` };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetchWithRetry(`${API_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 401 && retry) {
    saveToken(null);
    return request<T>(method, path, body, false);
  }

  const result: ApiResponse<T> = await response.json();
  if (!response.ok) {
    throw new ApiError(response.status, result.message);
  }
  return result.data;
}

// Like request, but asks for the answer as Server-Sent Events and passes every step and piece of text to onUpdate.
// fetch is used instead of EventSource because EventSource can only send GET requests.
// A backend that answers with plain JSON (an error, or an answer made without the agent) is handled as well
async function streamRequest<T>(path: string, body: unknown, onUpdate: (update: AnswerUpdate) => void, retry = true): Promise<T> {
  const currentToken = await ensureToken();
  const response = await fetchWithRetry(`${API_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${currentToken}`, "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });

  if (response.status === 401 && retry) {
    saveToken(null);
    return streamRequest<T>(path, body, onUpdate, false);
  }
  if (!(response.headers.get("Content-Type") ?? "").includes("text/event-stream") || response.body === null) {
    const result: ApiResponse<T> = await response.json();
    if (!response.ok) {
      throw new ApiError(response.status, result.message);
    }
    return result.data;
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) {
      throw new ApiError(502, "Jawaban terputus sebelum selesai.");
    }
    buffer += value;
    // Events are separated by a blank line; the last part may still be incomplete, so it stays in the buffer
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const event of events) {
      let name = "";
      let data = "";
      for (const line of event.split("\n")) {
        if (line.startsWith("event: ")) name = line.slice(7);
        if (line.startsWith("data: ")) data = line.slice(6);
      }
      const payload = data === "" ? {} : JSON.parse(data);
      if (name === "selesai") {
        await reader.cancel();
        return payload as T;
      }
      if (name === "galat") {
        await reader.cancel();
        throw new ApiError(500, payload.message ?? "Chatbot sedang bermasalah.");
      }
      if (name === "status") onUpdate({ kind: "status", text: payload.teks ?? "" });
      if (name === "teks") onUpdate({ kind: "text", text: payload.teks ?? "" });
      if (name === "ulang") onUpdate({ kind: "reset" });
    }
  }
}

// Converts a backend conversation into the shape used by the UI
function toConversation(raw: RawConversation): Conversation {
  return { id: raw.id, title: raw.judul };
}

// Converts a backend user into the shape used by the UI
function toAccount(raw: RawAccount): Account {
  return { id: raw.id, name: raw.nama, email: raw.email ?? "", role: raw.jenis };
}

// Converts a backend message into the shape used by the UI
function toMessage(raw: RawMessage): Message {
  return {
    id: raw.id,
    sender: raw.pengirim === "user" ? "user" : "bot",
    text: raw.isi,
    sources: (raw.sumber ?? []).map((source) => ({ title: source.judul, url: source.url })),
    sentAt: raw.dibuat_pada,
    favorite: raw.favorit,
    attachment: raw.lampiran ?? "",
  };
}

function attachmentBody(attachment: Attachment | null) {
  return attachment === null ? undefined : { nama: attachment.name, teks: attachment.text };
}

// Lists the conversations of this account, newest first
export async function listConversations(): Promise<Conversation[]> {
  const data = await request<RawConversation[]>("GET", "/percakapan");
  return data.map(toConversation);
}

// Creates an empty conversation
export async function createConversation(): Promise<Conversation> {
  return toConversation(await request<RawConversation>("POST", "/percakapan"));
}

// Deletes a conversation together with its messages
export async function deleteConversation(id: string): Promise<void> {
  await request<undefined>("DELETE", `/percakapan/${id}`);
}

// Renames a conversation and returns the title saved by the server
export async function renameConversation(id: string, title: string): Promise<Conversation> {
  return toConversation(await request<RawConversation>("PATCH", `/percakapan/${id}`, { judul: title }));
}

// Lists the messages of one conversation, oldest first
export async function listMessages(conversationId: string): Promise<Message[]> {
  const data = await request<RawMessage[]>("GET", `/percakapan/${conversationId}/pesan`);
  return data.map(toMessage);
}

// Sends a question into a conversation and returns the saved question and answer; onUpdate shows the answer as it is made
export async function sendMessage(
  conversationId: string,
  text: string,
  mode: AnswerMode,
  attachment: Attachment | null,
  onUpdate: (update: AnswerUpdate) => void,
): Promise<SendResult> {
  const body = { pertanyaan: text, mode: mode === "fast" ? "cepat" : "mendalam", lampiran: attachmentBody(attachment) };
  const data = await streamRequest<RawSendResult>(`/percakapan/${conversationId}/pesan`, body, onUpdate);
  return { title: data.judul, question: toMessage(data.pesan), answer: toMessage(data.jawaban) };
}

// Guest chats are not saved, so the messages on screen are sent along as history, and the file of this chat with every question
export async function sendGuestMessage(
  text: string,
  history: Message[],
  attachment: Attachment | null,
  onUpdate: (update: AnswerUpdate) => void,
): Promise<Message> {
  const riwayat = history.map((item) => ({ peran: item.sender === "user" ? "user" : "asisten", teks: item.text }));
  const data = await streamRequest<RawAnswer>("/tamu/pesan", { pertanyaan: text, riwayat, lampiran: attachmentBody(attachment) }, onUpdate);
  return {
    id: `guest-${Date.now()}`,
    sender: "bot",
    text: data.jawaban,
    sources: (data.sumber ?? []).map((source) => ({ title: source.judul, url: source.url })),
    sentAt: new Date().toISOString(),
    favorite: false,
    attachment: "",
  };
}

// Sends a file to be read; the server keeps nothing and returns its text.
// 404 means the server has file upload turned off
export async function uploadFile(file: File, retry = true): Promise<Attachment> {
  const currentToken = await ensureToken();
  const form = new FormData();
  form.append("berkas", file);
  const response = await fetchWithRetry(`${API_URL}/berkas`, {
    method: "POST",
    headers: { Authorization: `Bearer ${currentToken}` },
    body: form,
  });
  if (response.status === 401 && retry) {
    saveToken(null);
    return uploadFile(file, false);
  }
  if (response.status === 404) {
    throw new ApiError(404, "Unggah berkas belum aktif di server.");
  }
  const result: ApiResponse<RawFile> = await response.json();
  if (!response.ok) {
    throw new ApiError(response.status, result.message);
  }
  return { name: result.data.nama, text: result.data.teks, truncated: result.data.terpotong, pages: result.data.halaman };
}

// Stars or unstars a saved message of this account
export async function setFavorite(messageId: string, favorite: boolean): Promise<void> {
  await request<undefined>("PATCH", `/pesan/${messageId}/favorit`, { favorit: favorite });
}

// Lists the starred messages from every conversation of this account, newest first
export async function listFavorites(): Promise<FavoriteMessage[]> {
  const data = await request<RawFavorite[]>("GET", "/pesan/favorit");
  return data.map((raw) => ({ ...toMessage(raw), conversationId: raw.percakapan_id, conversationTitle: raw.judul_percakapan }));
}

// Returns who is using this device; a guest session is created when there is none
export async function getAccount(): Promise<Account> {
  const account = toAccount(await request<RawAccount>("GET", "/sesi"));
  if (account.role === "tamu" && token !== null) {
    saveToken(token, "guest");
  }
  return account;
}

// Sends one of the account forms with the current token, if any
async function postAccount<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetchWithRetry(`${API_URL}${path}`, { method: "POST", headers, body: JSON.stringify(body) });
  const result: ApiResponse<T> = await response.json();
  if (!response.ok) {
    throw new ApiError(response.status, result.message);
  }
  return result.data;
}

// Registers or logs in; the guest chat on screen is not carried into the account.
// Returns null when a new account has to confirm its email first; remember=false keeps the login only until the tab closes
export async function signIn(mode: "masuk" | "daftar", email: string, password: string, remember: boolean): Promise<Account | null> {
  const data = await postAccount<RawSignIn>(`/akun/${mode}`, { email, password, ingat: remember });
  if ("perlu_verifikasi" in data) {
    return null;
  }
  saveToken(data.token, "account", remember);
  return toAccount(data.pengguna);
}

let verifyPromise: Promise<Account> | null = null;

// Logs into the account whose email link was opened. A link works only once, so a second call
// (React runs effects twice in development) gets the same result instead of a new request
export function verifyEmail(code: string): Promise<Account> {
  verifyPromise ??= postAccount<RawSession & { ingat: boolean }>("/akun/verifikasi", { token: code }).then((data) => {
    saveToken(data.token, "account", data.ingat);
    return toAccount(data.pengguna);
  });
  return verifyPromise;
}

// Sends a new verification link; the backend answers the same way for unknown emails
export async function resendVerification(email: string, remember: boolean): Promise<void> {
  await postAccount<unknown>("/akun/kirim-ulang", { email, ingat: remember });
}

// Asks for a link to choose a new password; the backend answers the same way for unknown emails
export async function requestPasswordReset(email: string): Promise<void> {
  await postAccount<unknown>("/akun/lupa-password", { email });
}

// Saves a new password with the code from the reset email, then logs in on this device.
// The backend logs the account out of every other device
export async function resetPassword(code: string, password: string, remember: boolean): Promise<Account> {
  const data = await postAccount<RawSession>("/akun/atur-ulang", { token: code, password, ingat: remember });
  saveToken(data.token, "account", remember);
  return toAccount(data.pengguna);
}

// Admin only: saves one entry into the internal data used by the chatbot
export async function addKnowledge(title: string, content: string, keywords: string): Promise<void> {
  await request<unknown>("POST", "/admin/pengetahuan", { judul: title, isi: content, kata_kunci: keywords });
}

// Admin only: turns a registered account into an admin
export async function makeAdmin(email: string): Promise<void> {
  await request<unknown>("POST", "/admin/admin", { email });
}

// Deletes this device's login session from the backend and from the device
export async function logout(): Promise<void> {
  if (token === null) {
    return;
  }
  await request<undefined>("DELETE", "/sesi", undefined, false);
  saveToken(null);
}