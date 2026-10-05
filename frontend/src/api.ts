const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8080").replace(/\/$/, "");
const TOKEN_KEY = "chatbot_token";

export type Conversation = { id: number; title: string };
export type Message = { id: number; sender: "user" | "bot"; text: string; sources: string[] };
export type SendResult = { title: string; question: Message; answer: Message };

type ApiResponse<T> = { status: string; message: string; data: T };
type RawConversation = { id: number; judul: string };
type RawMessage = { id: number; pengirim: "user" | "asisten"; isi: string; sumber: string[] | null };
type RawSendResult = { judul: string; pesan: RawMessage; jawaban: RawMessage };

let token = readToken();
let loginPromise: Promise<string> | null = null;

// Reads the guest token saved on this device
function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

// Keeps the guest token in memory and on this device (null removes it)
function saveToken(value: string | null) {
  token = value;
  try {
    if (value === null) {
      localStorage.removeItem(TOKEN_KEY);
    } else {
      localStorage.setItem(TOKEN_KEY, value);
    }
  } catch {
    // storage is blocked, the token then only lives until the tab is closed
  }
}

// Asks the backend for a new guest session
async function loginGuest(): Promise<string> {
  const response = await fetch(`${API_URL}/sesi/tamu`, { method: "POST" });
  if (!response.ok) {
    throw new Error("Gagal masuk sebagai tamu");
  }
  const body: ApiResponse<{ token: string }> = await response.json();
  saveToken(body.data.token);
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

// Calls one backend endpoint with the guest token and returns its data
async function request<T>(method: string, path: string, body?: unknown, retry = true): Promise<T> {
  const currentToken = await ensureToken();
  const headers: Record<string, string> = { Authorization: `Bearer ${currentToken}` };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_URL}${path}`, {
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
    throw new Error(result.message);
  }
  return result.data;
}

// Converts a backend conversation into the shape used by the UI
function toConversation(raw: RawConversation): Conversation {
  return { id: raw.id, title: raw.judul };
}

// Converts a backend message into the shape used by the UI
function toMessage(raw: RawMessage): Message {
  return {
    id: raw.id,
    sender: raw.pengirim === "user" ? "user" : "bot",
    text: raw.isi,
    sources: raw.sumber ?? [],
  };
}

// Lists the conversations of this guest, newest first
export async function listConversations(): Promise<Conversation[]> {
  const data = await request<RawConversation[]>("GET", "/percakapan");
  return data.map(toConversation);
}

// Creates an empty conversation
export async function createConversation(): Promise<Conversation> {
  return toConversation(await request<RawConversation>("POST", "/percakapan"));
}

// Deletes a conversation together with its messages
export async function deleteConversation(id: number): Promise<void> {
  await request<undefined>("DELETE", `/percakapan/${id}`);
}

// Lists the messages of one conversation, oldest first
export async function listMessages(conversationId: number): Promise<Message[]> {
  const data = await request<RawMessage[]>("GET", `/percakapan/${conversationId}/pesan`);
  return data.map(toMessage);
}

// Sends a question into a conversation and returns the saved question and answer
export async function sendMessage(conversationId: number, text: string): Promise<SendResult> {
  const data = await request<RawSendResult>("POST", `/percakapan/${conversationId}/pesan`, { pertanyaan: text });
  return { title: data.judul, question: toMessage(data.pesan), answer: toMessage(data.jawaban) };
}

// Deletes this device's login session from the backend and from the device
export async function logout(): Promise<void> {
  if (token === null) {
    return;
  }
  await request<undefined>("DELETE", "/sesi", undefined, false);
  saveToken(null);
}