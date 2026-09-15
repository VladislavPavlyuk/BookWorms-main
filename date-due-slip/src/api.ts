import * as SecureStore from "expo-secure-store";
import { DEFAULT_API } from "./theme";
import type {
  Book,
  Exchange,
  Message,
  Paginated,
  Post,
  Shelf,
  User,
} from "./types";

const ACCESS = "dds_access";
const REFRESH = "dds_refresh";
const API_KEY = "dds_api";

export async function getApiBase(): Promise<string> {
  return (await SecureStore.getItemAsync(API_KEY)) || DEFAULT_API;
}

export async function setApiBase(url: string) {
  await SecureStore.setItemAsync(API_KEY, url.replace(/\/$/, ""));
}

export async function getAccess() {
  return SecureStore.getItemAsync(ACCESS);
}

export async function setTokens(access: string, refresh: string) {
  await SecureStore.setItemAsync(ACCESS, access);
  await SecureStore.setItemAsync(REFRESH, refresh);
}

export async function clearTokens() {
  await SecureStore.deleteItemAsync(ACCESS);
  await SecureStore.deleteItemAsync(REFRESH);
}

type Opts = {
  method?: string;
  body?: unknown;
  auth?: boolean;
};

function flattenError(payload: unknown): string {
  if (!payload || typeof payload !== "object") return String(payload ?? "error");
  const p = payload as Record<string, unknown>;
  if (typeof p.detail === "string") return p.detail;
  if (Array.isArray(p.errors)) return p.errors.map(String).join("\n");
  return Object.entries(p)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : JSON.stringify(v)}`)
    .join("\n");
}

export class ApiError extends Error {
  status: number;
  payload: unknown;
  constructor(status: number, payload: unknown) {
    super(flattenError(payload) || `HTTP ${status}`);
    this.status = status;
    this.payload = payload;
  }
}

async function refreshAccess(base: string): Promise<string | null> {
  const refresh = await SecureStore.getItemAsync(REFRESH);
  if (!refresh) return null;
  const res = await fetch(`${base}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) return null;
  const data = (await res.json()) as { access: string };
  await SecureStore.setItemAsync(ACCESS, data.access);
  return data.access;
}

export async function api<T>(path: string, opts: Opts = {}): Promise<T> {
  const base = await getApiBase();
  const headers: Record<string, string> = { Accept: "application/json" };
  let token = opts.auth === false ? null : await getAccess();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";

  const exec = (t: string | null) => {
    const h = { ...headers };
    if (t) h.Authorization = `Bearer ${t}`;
    else delete h.Authorization;
    return fetch(`${base}${path}`, {
      method: opts.method || "GET",
      headers: h,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  };

  let res = await exec(token);
  if (res.status === 401 && opts.auth !== false) {
    const next = await refreshAccess(base);
    if (next) res = await exec(next);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { detail: text.slice(0, 200) };
    }
  }
  if (!res.ok) throw new ApiError(res.status, payload);
  return payload as T;
}

export const AuthApi = {
  login: (username: string, password: string) =>
    api<{ access: string; refresh: string; user: User }>("/api/auth/login/", {
      method: "POST",
      body: { username, password },
      auth: false,
    }),
  register: (username: string, email: string, password: string, biography = "") =>
    api<{ access?: string; refresh?: string; user?: User; needs_activation?: boolean; detail?: string }>(
      "/api/auth/register/",
      { method: "POST", body: { username, email, password, biography }, auth: false }
    ),
  me: () => api<User>("/api/auth/me/"),
};

export const FeedApi = {
  list: (page = 1, filter?: "my") =>
    api<Paginated<Post>>(`/api/posts/?page=${page}${filter === "my" ? "&filter=my" : ""}`),
  create: (body: { title: string; text: string; book_id?: number; confirm_new_post?: boolean }) =>
    api<Post>("/api/posts/create/", { method: "POST", body }),
  like: (id: number) => api<{ liked: boolean; likes_count: number }>(`/api/posts/${id}/like/`, { method: "POST" }),
  comment: (id: number, text: string) =>
    api(`/api/posts/${id}/comments/`, { method: "POST", body: { text } }),
};

export const ShelfApi = {
  mine: () => api<{ shelves: Shelf[]; pending_returns: Shelf[] }>("/api/shelf/"),
  addIsbn: (isbn: string) => api<Shelf>("/api/shelf/isbn/", { method: "POST", body: { isbn } }),
  addManual: (body: Record<string, string>) =>
    api<Shelf>("/api/shelf/manual/", { method: "POST", body }),
  remove: (id: number) => api(`/api/shelf/${id}/`, { method: "DELETE" }),
  returnBook: (id: number) => api(`/api/shelf/${id}/return/`, { method: "POST" }),
  confirmReturn: (id: number) => api(`/api/shelf/${id}/confirm-return/`, { method: "POST" }),
  readerAge: (id: number, min_readers_age: number, max_readers_age: number) =>
    api(`/api/shelf/${id}/reader-age/`, { method: "POST", body: { min_readers_age, max_readers_age } }),
};

export const SlipApi = {
  list: () => api<{ borrowed: Shelf[]; lent: Shelf[]; loan_days: number }>("/api/slips/"),
};

export const BrowseApi = {
  list: () => api<{ others: Shelf[]; my_owned: Shelf[] }>("/api/browse/"),
  user: (id: number) =>
    api<{ user: User; is_own: boolean; shelves: Shelf[] }>(`/api/users/${id}/shelf/`),
  book: (id: number) =>
    api<{ book: Book; holders: Shelf[]; posts: Post[] }>(`/api/books/${id}/`),
};

export const ExchangeApi = {
  list: () =>
    api<{ pending_in: Exchange[]; pending_out: Exchange[]; history: Exchange[] }>("/api/exchanges/"),
  create: (target_shelf_id: number, offer_shelf_id?: number | null) =>
    api("/api/exchanges/create/", {
      method: "POST",
      body: { target_shelf_id, offer_shelf_id: offer_shelf_id || null },
    }),
  accept: (id: number) => api(`/api/exchanges/${id}/accept/`, { method: "POST" }),
  reject: (id: number) => api(`/api/exchanges/${id}/reject/`, { method: "POST" }),
  cancel: (id: number) => api(`/api/exchanges/${id}/cancel/`, { method: "POST" }),
};

export const MsgApi = {
  partners: () => api<User[]>("/api/messages/partners/"),
  thread: (id: number) => api<{ partner: User; messages: Message[] }>(`/api/messages/${id}/`),
  send: (id: number, body: string) =>
    api<Message>(`/api/messages/${id}/`, { method: "POST", body: { body } }),
};
