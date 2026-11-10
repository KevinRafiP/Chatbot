import { runPython } from "./pythonRunner"; import { getCaptchaToken } from "./captcha";

const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8080").replace(/\/$/, "");
const ACCOUNT_TOKEN_KEY = "chatbot_token";
const GUEST_TOKEN_KEY = "chatbot_guest_token";

// answering is true while the server is still making an answer in this conversation;
// failed is true when its last answer failed and the question was not sent again yet
export type Conversation = { id: string; title: string; pinned: boolean; answering: boolean; failed: boolean };
export type Source = { title: string; url: string };
export type Message = {
  id: string;
  sender: "user" | "bot";
  text: string;
  sources: Source[];
  sentAt: string;
  favorite: boolean;
  attachment: string;
  rating: Rating;
  note?: string;
  retry?: { attachment: Attachment | null };
  // follow-up questions suggested with a fresh answer; never saved, so only the newest answer has them
  suggestions?: string[];
};
export type Rating = 1 | -1 | 0;
// Text read from an uploaded file; it is sent along with the next question
export type Attachment = { name: string; text: string; truncated: boolean; pages: number | null };
export type FavoriteMessage = Message & { conversationId: string; conversationTitle: string };
export type SendResult = { title: string; question: Message; answer: Message };
// A conversation found by searching, with the part of a message where the words were found (empty when only the title matched)
export type SearchResult = { conversation: Conversation; snippet: string };
// An answer still being made on the server: the question it answers, and the saved question and answer once it is done.
// finished is true for an answer that already failed, so it is not shown as being written
export type RunningAnswer = { question: Message; finished: boolean; result: Promise<SendResult> };
export type Role = "tamu" | "user" | "admin";
export type Account = { id: string; name: string; email: string; role: Role };

// What the backend reports while an answer is being made: a step such as "Mencari: ...", a new piece of the
// answer, or "reset" when the text so far was only a lead-in before a search and has to be cleared
export type AnswerUpdate = { kind: "status"; text: string } | { kind: "text"; text: string } | { kind: "reset" };
// "fast" answers quickly with fewer searches, "deep" thinks longer and may read more sources
export type AnswerMode = "fast" | "deep";
// Speed and token use of many answers; profile is empty for the total of all answers
export type PerformanceStats = {
  profile: string;
  count: number;
  failed: number;
  avgMs: number;
  p90Ms: number;
  avgTokens: number;
  tokensIn: number;
  tokensOut: number;
};
// One answer or conversation summary; the question and answer text are never stored
export type PerformanceEntry = {
  profile: string;
  ok: boolean;
  error: string;
  durationMs: number;
  tokensIn: number;
  tokensOut: number;
  modelCalls: number;
  tools: string[];
  createdAt: string;
  // see PerformanceAccount.key; accountName is empty for guests and logs without an account
  account: string;
  accountName: string;
};
// Answers asked by one account. key is the account id, "tamu" for all guests together,
// or "lain" for logs from before accounts were recorded and from deleted accounts
export type PerformanceAccount = {
  key: string;
  name: string;
  email: string;
  role: string;
  count: number;
  failed: number;
  avgMs: number;
  tokensIn: number;
  tokensOut: number;
  lastAt: string;
};
// Likes and dislikes from users; profile is empty for the total
export type RatingStats = { profile: string; likes: number; dislikes: number };
// A disliked answer with the question before it, both cut short; empty when the server hides message text
export type DislikedAnswer = { profile: string; question: string; answer: string; ratedAt: string };
// The last 1, 7, or 30 days, or dates the admin picked (YYYY-MM-DD in the browser's time zone, both days included)
export type PerformanceRange = { days: number } | { from: string; to: string };
export type PerformanceReport = {
  days: number;
  from: string;
  to: string;
  total: PerformanceStats;
  byProfile: PerformanceStats[];
  tools: { name: string; count: number }[];
  // every account in the period, even when the report is filtered to one account
  byAccount: PerformanceAccount[];
  account: string;
  ratings: RatingStats[];
  disliked: DislikedAnswer[];
};

// One page of the newest performance logs; total counts every log in the period
export type PerformanceRecentPage = { entries: PerformanceEntry[]; total: number; page: number; perPage: number };

type ApiResponse<T> = { status: string; message: string; data: T };
type RawConversation = { id: string; judul: string; disematkan?: boolean; menjawab?: boolean; gagal?: boolean };
type RawRunning = { pertanyaan: string; lampiran?: string; dimulai_pada: string; selesai?: boolean };
type RawSource = { judul: string; url: string };
type RawMessage = {
  id: string;
  pengirim: "user" | "asisten";
  isi: string;
  sumber: RawSource[] | null;
  favorit: boolean;
  penilaian?: number;
  lampiran?: string;
  dibuat_pada: string;
};
type RawFavorite = RawMessage & { percakapan_id: string; judul_percakapan: string };
type RawSendResult = { judul: string; pesan: RawMessage; jawaban: RawMessage; saran?: string[] };
type RawAccount = { id: string; nama: string; jenis: Role; email?: string };
type RawSession = { token: string; pengguna: RawAccount };
type RawSignIn = RawSession | { perlu_verifikasi: true; email: string };
type RawAnswer = { jawaban: string; sumber: RawSource[] | null; saran?: string[] };
type RawFile = { nama: string; teks: string; terpotong: boolean; halaman: number | null };
type RawStats = {
  profil: string;
  jumlah: number;
  gagal: number;
  rata_lama_ms: number;
  p90_lama_ms: number;
  rata_token: number;
  token_masuk: number;
  token_keluar: number;
};
type RawPerformanceEntry = {
  profil: string;
  berhasil: boolean;
  galat?: string;
  lama_ms: number;
  token_masuk: number;
  token_keluar: number;
  panggilan_llm: number;
  alat: string[] | null;
  dibuat_pada: string;
  akun?: string;
  nama_akun?: string;
};
type RawAccountStats = {
  akun: string;
  nama: string;
  email?: string;
  jenis: string;
  jumlah: number;
  gagal: number;
  rata_lama_ms: number;
  token_masuk: number;
  token_keluar: number;
  terakhir: string;
};
type RawPerformance = {
  hari: number;
  dari: string;
  sampai: string;
  semua: RawStats;
  per_profil: RawStats[];
  alat: { nama: string; jumlah: number }[];
  per_akun?: RawAccountStats[];
  akun?: string;
  penilaian?: { profil: string; suka: number; tidak_suka: number }[];
  tidak_disukai?: { profil: string; pertanyaan: string; jawaban: string; dinilai_pada: string }[];
};

type RawRecentPage = { baris: RawPerformanceEntry[]; total: number; halaman: number; per_halaman: number };

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

// Asks the backend whether the agent and its AI model can answer right now. An unreachable backend counts as
// connected here, because the "server is waking" notice already covers that case
export async function getAgentStatus(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/status-agen`);
    if (!response.ok) {
      return true;
    }
    const body: ApiResponse<{ terhubung: boolean }> = await response.json();
    return body.data.terhubung;
  } catch {
    return true;
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
      // the user pressed stop: no retry and no "server is waking" notice
      if (init?.signal?.aborted) {
        wakingListener?.(false);
        throw error;
      }
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

// Opens a request that answers with Server-Sent Events; an expired token is replaced once like in request
async function openStream(method: string, path: string, body: unknown, signal?: AbortSignal, retry = true): Promise<Response> {
  const currentToken = await ensureToken();
  const headers: Record<string, string> = { Authorization: `Bearer ${currentToken}`, Accept: "text/event-stream" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetchWithRetry(`${API_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (response.status === 401 && retry) {
    saveToken(null);
    return openStream(method, path, body, signal, false);
  }
  return response;
}

// Like request, but asks for the answer as Server-Sent Events and passes every step and piece of text to onUpdate.
// fetch is used instead of EventSource because EventSource cannot send the token header.
// signal only stops this page from listening: an account's answer keeps being made on the server until it is stopped
// with stopServerAnswer, while a guest's answer stops with the connection
async function streamRequest<T>(
  path: string,
  body: unknown,
  onUpdate: (update: AnswerUpdate) => void,
  signal?: AbortSignal,
): Promise<T> {
  return readStream<T>(await openStream("POST", path, body, signal), onUpdate);
}

// Reads the events of an answer until it is done. "mulai" comes first when joining an answer that is already running.
// A backend that answers with plain JSON (an error, or an answer made without the agent) is handled as well
async function readStream<T>(
  response: Response,
  onUpdate: (update: AnswerUpdate) => void,
  onStart?: (raw: RawRunning) => void,
): Promise<T> {
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
      if (name === "mulai") onStart?.(payload);
      if (name === "status") onUpdate({ kind: "status", text: payload.teks ?? "" });
      if (name === "teks") onUpdate({ kind: "text", text: payload.teks ?? "" });
      if (name === "ulang") onUpdate({ kind: "reset" });
      if (name === "jalankan_kode") void runAgentCode(payload);
    }
  }
}

// Runs the Python code the agent asked for on this device, then sends the result back so the answer can continue.
// The agent stops waiting by itself, so a failed send is only logged
async function runAgentCode(payload: { id?: string; kode?: string; batas_detik?: number }): Promise<void> {
  if (typeof payload.id !== "string" || typeof payload.kode !== "string") return;
  const result = await runPython(payload.kode, payload.batas_detik ?? 15);
  try {
    await request("POST", "/kode/hasil", { id: payload.id, keluaran: result.output, galat: result.error, hasil: result.result });
  } catch (err) {
    console.warn("Python result was not sent", err);
  }
}

// Converts a backend conversation into the shape used by the UI
function toConversation(raw: RawConversation): Conversation {
  return {
    id: raw.id,
    title: raw.judul,
    pinned: raw.disematkan === true,
    answering: raw.menjawab === true,
    failed: raw.gagal === true,
  };
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
    rating: raw.penilaian === 1 || raw.penilaian === -1 ? raw.penilaian : 0,
  };
}

function attachmentBody(attachment: Attachment | null) {
  return attachment === null ? undefined : { nama: attachment.name, teks: attachment.text };
}

// Lists the conversations of this account: pinned ones first, then the newest
export async function listConversations(): Promise<Conversation[]> {
  const data = await request<RawConversation[]>("GET", "/percakapan");
  return data.map(toConversation);
}

// Creates an empty conversation
export async function createConversation(): Promise<Conversation> {
  return toConversation(await request<RawConversation>("POST", "/percakapan"));
}

// Deletes a conversation from the list; the server keeps its data for the performance report
export async function deleteConversation(id: string): Promise<void> {
  await request<undefined>("DELETE", `/percakapan/${id}`);
}

// Renames a conversation and returns the title saved by the server
export async function renameConversation(id: string, title: string): Promise<Conversation> {
  return toConversation(await request<RawConversation>("PATCH", `/percakapan/${id}`, { judul: title }));
}

// Pins a conversation to the top of the list, or unpins it
export async function pinConversation(id: string, pinned: boolean): Promise<void> {
  await request<undefined>("PATCH", `/percakapan/${id}/sematkan`, { sematkan: pinned });
}

// Lists the messages of one conversation, oldest first
export async function listMessages(conversationId: string): Promise<Message[]> {
  const data = await request<RawMessage[]>("GET", `/percakapan/${conversationId}/pesan`);
  return data.map(toMessage);
}

// Sends a question into a conversation and returns the saved question and answer; onUpdate shows the answer as it is made.
// replaceFrom is the id of an earlier question: it and every message after it are replaced, for editing a question
// or making its answer again
export async function sendMessage(
  conversationId: string,
  text: string,
  mode: AnswerMode,
  attachment: Attachment | null,
  onUpdate: (update: AnswerUpdate) => void,
  signal?: AbortSignal,
  replaceFrom?: string,
): Promise<SendResult> {
  const body = {
    pertanyaan: text,
    mode: mode === "fast" ? "cepat" : "mendalam",
    lampiran: attachmentBody(attachment),
    ganti_dari: replaceFrom,
  };
  return toSendResult(await streamRequest<RawSendResult>(`/percakapan/${conversationId}/pesan`, body, onUpdate, signal));
}

// Restarts the answer being made with an extra instruction typed while the AI was still answering;
// the question becomes the old question plus the instruction, and the new answer comes back like sendMessage
export async function steerAnswer(
  conversationId: string,
  extra: string,
  onUpdate: (update: AnswerUpdate) => void,
  signal?: AbortSignal,
): Promise<SendResult> {
  return toSendResult(await streamRequest<RawSendResult>(`/percakapan/${conversationId}/arahan`, { tambahan: extra }, onUpdate, signal));
}

// Finds conversations whose title or messages contain the words, newest first
export async function searchConversations(query: string): Promise<SearchResult[]> {
  const data = await request<(RawConversation & { cuplikan: string })[]>("GET", `/percakapan/cari?q=${encodeURIComponent(query)}`);
  return data.map((raw) => ({ conversation: toConversation(raw), snippet: raw.cuplikan }));
}

// Joins the answer still being made in a conversation, for example after a refresh or after coming back to it.
// Every step and piece of text so far is replayed through onUpdate first. An answer that failed while nobody watched
// comes back too and ends with an error. Returns null when there is neither
export async function resumeAnswer(
  conversationId: string,
  onUpdate: (update: AnswerUpdate) => void,
  signal?: AbortSignal,
): Promise<RunningAnswer | null> {
  const response = await openStream("GET", `/percakapan/${conversationId}/jawaban`, undefined, signal);
  if (response.status === 204) {
    return null;
  }
  return new Promise((resolve, reject) => {
    const done = readStream<RawSendResult>(response, onUpdate, (raw) => {
      const result = done.then(toSendResult);
      // a page that left this chat never waits for the result, so its failure must not show as an uncaught error
      result.catch(() => undefined);
      resolve({ question: toRunningQuestion(raw), finished: raw.selesai === true, result });
    });
    // without "mulai" the answer cannot be shown; after resolve this does nothing
    done.then(() => reject(new ApiError(502, "Jawaban terputus sebelum selesai.")), reject);
  });
}

// Stops the answer being made in a conversation; closing the connection alone no longer stops it
export async function stopServerAnswer(conversationId: string): Promise<void> {
  await request<undefined>("POST", `/percakapan/${conversationId}/berhenti`);
}

function toSendResult(raw: RawSendResult): SendResult {
  return { title: raw.judul, question: toMessage(raw.pesan), answer: { ...toMessage(raw.jawaban), suggestions: raw.saran } };
}

// The question of a running answer, shown like a question that was just sent
function toRunningQuestion(raw: RawRunning): Message {
  return {
    id: `draft-${Date.parse(raw.dimulai_pada) || Date.now()}`,
    sender: "user",
    text: raw.pertanyaan,
    sources: [],
    sentAt: raw.dimulai_pada,
    favorite: false,
    attachment: raw.lampiran ?? "",
    rating: 0,
  };
}

// Guest chats are not saved, so the messages on screen are sent along as history, and the file of this chat with every question
export async function sendGuestMessage(
  text: string,
  history: Message[],
  attachment: Attachment | null,
  onUpdate: (update: AnswerUpdate) => void,
signal?: AbortSignal,
): Promise<Message> {
  // failed or stopped questions on screen were never answered, so they are not part of the history
  const riwayat = history
    .filter((item) => item.note === undefined)
    .map((item) => ({ peran: item.sender === "user" ? "user" : "asisten", teks: item.text }));
  const body = { pertanyaan: text, riwayat, lampiran: attachmentBody(attachment) };
  const data = await streamRequest<RawAnswer>("/tamu/pesan", body, onUpdate, signal);
  return {
    id: `guest-${Date.now()}`,
    sender: "bot",
    text: data.jawaban,
    sources: (data.sumber ?? []).map((source) => ({ title: source.judul, url: source.url })),
    sentAt: new Date().toISOString(),
    favorite: false,
    attachment: "",
    rating: 0,
    suggestions: data.saran,
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

// Likes (1) or dislikes (-1) a saved answer; 0 removes the rating
export async function setRating(messageId: string, rating: Rating): Promise<void> {
  await request<undefined>("PATCH", `/pesan/${messageId}/penilaian`, { penilaian: rating });
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

// Sends one of the account forms with the current token, if any; captcha adds a Turnstile token first (login only)
async function postAccount<T>(path: string, body: unknown, captcha = false): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const captchaToken = captcha ? await getCaptchaToken() : null;
  if (captchaToken !== null) {
    headers["X-Captcha-Token"] = captchaToken;
  }
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
  const data = await postAccount<RawSignIn>(`/akun/${mode}`, { email, password, ingat: remember }, mode === "masuk");
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

// Midnight at the start of a YYYY-MM-DD day in the browser's time zone, moved by extraDays, as an RFC 3339 time
function startOfDay(date: string, extraDays = 0): string {
  const [year, month, day] = date.split("-").map(Number);
  return new Date(year, month - 1, day + extraDays).toISOString();
}

// account is empty for all accounts
function rangeQuery(range: PerformanceRange, account: string): string {
  const period =
    "days" in range
      ? `hari=${range.days}`
      : `dari=${encodeURIComponent(startOfDay(range.from))}&sampai=${encodeURIComponent(startOfDay(range.to, 1))}`;
  return account === "" ? period : `${period}&akun=${encodeURIComponent(account)}`;
}

// Admin only: answer speed, token use, and tool use over the last 1, 7, or 30 days, or between two picked dates,
// for every account or for one account
export async function getPerformance(range: PerformanceRange, account = ""): Promise<PerformanceReport> {
  const data = await request<RawPerformance>("GET", `/admin/kinerja?${rangeQuery(range, account)}`)
  return {
    days: data.hari,
    from: data.dari,
    to: data.sampai,
    total: toStats(data.semua),
    byProfile: data.per_profil.map(toStats),
    tools: data.alat.map((tool) => ({ name: tool.nama, count: tool.jumlah })),
    byAccount: (data.per_akun ?? []).map((row) => ({
      key: row.akun,
      name: row.nama,
      email: row.email ?? "",
      role: row.jenis,
      count: row.jumlah,
      failed: row.gagal,
      avgMs: row.rata_lama_ms,
      tokensIn: row.token_masuk,
      tokensOut: row.token_keluar,
      lastAt: row.terakhir,
    })),
    account: data.akun ?? "",
    ratings: (data.penilaian ?? []).map((row) => ({ profile: row.profil, likes: row.suka, dislikes: row.tidak_suka })),
    disliked: (data.tidak_disukai ?? []).map((row) => ({
      profile: row.profil,
      question: row.pertanyaan,
      answer: row.jawaban,
      ratedAt: row.dinilai_pada,
    })),
  };
}

// Admin only: one page of the newest performance logs in the period; the server moves a page past the end to the last one
export async function getPerformanceRecent(range: PerformanceRange, account: string, page: number): Promise<PerformanceRecentPage> {
  const data = await request<RawRecentPage>("GET", `/admin/kinerja/terbaru?${rangeQuery(range, account)}&halaman=${page}`);
  return {
    entries: data.baris.map((entry) => ({
      profile: entry.profil,
      ok: entry.berhasil,
      error: entry.galat ?? "",
      durationMs: entry.lama_ms,
      tokensIn: entry.token_masuk,
      tokensOut: entry.token_keluar,
      modelCalls: entry.panggilan_llm,
      account: entry.akun ?? "",
      accountName: entry.nama_akun ?? "",
      tools: entry.alat ?? [],
      createdAt: entry.dibuat_pada,
    })),
    total: data.total,
    page: data.halaman,
    perPage: data.per_halaman,
  };
}

function toStats(raw: RawStats): PerformanceStats {
  return {
    profile: raw.profil,
    count: raw.jumlah,
    failed: raw.gagal,
    avgMs: raw.rata_lama_ms,
    p90Ms: raw.p90_lama_ms,
    avgTokens: raw.rata_token,
    tokensIn: raw.token_masuk,
    tokensOut: raw.token_keluar,
  };
}

// Deletes this device's login session from the backend and from the device
export async function logout(): Promise<void> {
  if (token === null) {
    return;
  }
  await request<undefined>("DELETE", "/sesi", undefined, false);
  saveToken(null);
}