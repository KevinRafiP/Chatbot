const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8080").replace(/\/$/, "");
const ACCOUNT_TOKEN_KEY = "chatbot_token";
const GUEST_TOKEN_KEY = "chatbot_guest_token";

export type Conversation = { id: string; title: string };
export type Source = { title: string; url: string };
export type Message = { id: string; sender: "user" | "bot"; text: string; sources: Source[] };
export type SendResult = { title: string; question: Message; answer: Message };
export type Role = "tamu" | "user" | "admin";
export type Account = { id: string; name: string; email: string; role: Role };

type ApiResponse<T> = { status: string; message: string; data: T };
type RawConversation = { id: string; judul: string };
type RawSource = { judul: string; url: string };
type RawMessage = { id: string; pengirim: "user" | "asisten"; isi: string; sumber: RawSource[] | null };
type RawSendResult = { judul: string; pesan: RawMessage; jawaban: RawMessage };
type RawAccount = { id: string; nama: string; jenis: Role; email?: string };
type RawSession = { token: string; pengguna: RawAccount };
type RawAnswer = { jawaban: string; sumber: RawSource[] | null };

// Render free puts the backend to sleep; these are the waits before each new try while it wakes up (about 2.5 minutes in total)
const RETRY_DELAYS_MS = [5000, 10000, 15000, 20000, 30000, 30000, 40000];
// Render sleeps after 15 minutes without any request, so a server that answered less than 14 minutes ago is still awake
const AWAKE_WINDOW_MS = 14 * 60 * 1000;
const AWAKE_AT_KEY = "chatbot_awake_at";

// Error with the HTTP status, so the UI can tell a guest limit or rate limit from other failures
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let token = readToken(localStorage, ACCOUNT_TOKEN_KEY) ?? readToken(localStorage, GUEST_TOKEN_KEY);
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

// Both tokens live in localStorage; the guest token is kept too, so closing the tab does not reset the guest message limit
function saveToken(value: string | null, kind: "account" | "guest" = "account") {
  token = value;
  try {
    localStorage.removeItem(ACCOUNT_TOKEN_KEY);
    localStorage.removeItem(GUEST_TOKEN_KEY);
    if (value !== null) {
      localStorage.setItem(kind === "account" ? ACCOUNT_TOKEN_KEY : GUEST_TOKEN_KEY, value);
    }
  } catch {
    // storage is blocked, the token then only lives in memory
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
        if (response.status < 500) {
          markAwake();
        }
        return response;
      }
    } catch (error) {
      if (lastTry) {
        wakingListener?.(false);
        throw error;
      }
    }
    wakingListener?.(true);
    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[attempt]));
  }
}

// Remembers in this browser when the backend last answered
function markAwake() {
  try {
    localStorage.setItem(AWAKE_AT_KEY, String(Date.now()));
  } catch {
    // storage is blocked, the next visit just pings again
  }
}

// True when this browser got an answer from the backend within the last 14 minutes
function recentlyAwake(): boolean {
  try {
    return Date.now() - Number(localStorage.getItem(AWAKE_AT_KEY) ?? 0) < AWAKE_WINDOW_MS;
  } catch {
    return false;
  }
}

// Wakes the backend when a visitor arrives, at most once per 14 minutes per browser, so refreshing does not spam it
export async function warmUp(): Promise<void> {
  if (recentlyAwake()) {
    return;
  }
  try {
    await fetchWithRetry(`${API_URL}/kesehatan`);
  } catch {
    // the next request will try again
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
  };
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

// Sends a question into a conversation and returns the saved question and answer
export async function sendMessage(conversationId: string, text: string): Promise<SendResult> {
  const data = await request<RawSendResult>("POST", `/percakapan/${conversationId}/pesan`, { pertanyaan: text });
  return { title: data.judul, question: toMessage(data.pesan), answer: toMessage(data.jawaban) };
}

// Guest chats are not saved, so the messages on screen are sent along as history
export async function sendGuestMessage(text: string, history: Message[]): Promise<Message> {
  const riwayat = history.map((item) => ({ peran: item.sender === "user" ? "user" : "asisten", teks: item.text }));
  const data = await request<RawAnswer>("POST", "/tamu/pesan", { pertanyaan: text, riwayat });
  return {
    id: `guest-${Date.now()}`,
    sender: "bot",
    text: data.jawaban,
    sources: (data.sumber ?? []).map((source) => ({ title: source.judul, url: source.url })),
  };
}

// Returns who is using this device; a guest session is created when there is none
export async function getAccount(): Promise<Account> {
  const account = toAccount(await request<RawAccount>("GET", "/sesi"));
  if (account.role === "tamu" && token !== null) {
    saveToken(token, "guest");
  }
  return account;
}

// Registers or logs in; the guest chat on screen is not carried into the account
export async function signIn(mode: "masuk" | "daftar", email: string, password: string): Promise<Account> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetchWithRetry(`${API_URL}/akun/${mode}`, {
    method: "POST",
    headers,
    body: JSON.stringify({ email, password }),
  });
  const result: ApiResponse<RawSession> = await response.json();
  if (!response.ok) {
    throw new ApiError(response.status, result.message);
  }
  saveToken(result.data.token, "account");
  return toAccount(result.data.pengguna);
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