import * as SecureStore from "expo-secure-store";
import { DEFAULT_API } from "./theme";
import {
  BookCopyDetail,
  Book,
  BookBrowseGroup,
  Comment,
  CopyEvent,
  Exchange,
  LoanHandoff,
  Message,
  Paginated,
  Post,
  QueueEntry,
  Shelf,
  User,
} from "./types";

const ACCESS = "dds_access";
const REFRESH = "dds_refresh";
const API_KEY = "dds_api";

/** Нормалізація URL: без слеша в кінці, http://, старі порти QNAP → 18088. */
export function normalizeApiBase(raw: string | null | undefined): string {
  let u = (raw || "").trim().replace(/\/$/, "");
  if (!u) return DEFAULT_API;
  if (!/^https?:\/\//i.test(u)) u = `http://${u}`;
  u = u.replace(/:(8088|8080)(?=\/|$)/, ":18088");
  return u;
}

export async function getApiBase(): Promise<string> {
  const stored = await SecureStore.getItemAsync(API_KEY);
  const normalized = normalizeApiBase(stored || DEFAULT_API);
  if (stored && stored.replace(/\/$/, "") !== normalized) {
    await SecureStore.setItemAsync(API_KEY, normalized);
  }
  return normalized;
}

export async function setApiBase(url: string) {
  await SecureStore.setItemAsync(API_KEY, normalizeApiBase(url));
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
  if (opts.body !== undefined) headers["Content-Type"] = "application/json; charset=utf-8";

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
    api<{
      access?: string;
      refresh?: string;
      user?: User;
      needs_activation?: boolean;
      detail?: string;
      email_sent?: boolean;
      server_error?: string | null;
      web3forms_payload?: Record<string, unknown> | null;
      web3forms_browser_url?: string;
      activation_url?: string;
      activation_timeout_minutes?: number;
    }>("/api/auth/register/", {
      method: "POST",
      body: { username, email, password, biography },
      auth: false,
    }),
  me: () => api<User>("/api/auth/me/"),
  updateMe: (body: { username?: string; biography?: string }) =>
    api<User>("/api/auth/me/", { method: "PATCH", body }),
};

export type FeedSearch = {
  q?: string;
  isbn?: string;
  authors?: string;
  publisher?: string;
  publish_date?: string;
  age_min?: string;
  age_max?: string;
};

function bookQuery(page: number, search?: FeedSearch) {
  const p = new URLSearchParams();
  p.set("page", String(page));
  if (search) {
    (Object.keys(search) as (keyof FeedSearch)[]).forEach((k) => {
      const v = (search[k] || "").trim();
      if (v) p.set(k, v);
    });
  }
  return p.toString();
}

export const FeedApi = {
  list: (page = 1, filter?: "my", fromId?: number | null) => {
    const p = new URLSearchParams();
    p.set("page", String(page));
    if (filter === "my") p.set("filter", "my");
    if (fromId) p.set("from_id", String(fromId));
    return api<Paginated<Post>>(`/api/posts/?${p.toString()}`);
  },
  get: (id: number) => api<Post>(`/api/posts/${id}/`),
  create: (body: { title: string; text: string; book_id?: number; confirm_new_post?: boolean }) =>
    api<Post>("/api/posts/create/", { method: "POST", body }),
  update: (id: number, body: { title: string; text: string }) =>
    api<Post>(`/api/posts/${id}/`, { method: "PATCH", body }),
  remove: (id: number) => api(`/api/posts/${id}/`, { method: "DELETE" }),
  like: (id: number) => api<{ liked: boolean; likes_count: number }>(`/api/posts/${id}/like/`, { method: "POST" }),
  comment: (id: number, text: string) =>
    api<Comment>(`/api/posts/${id}/comments/`, { method: "POST", body: { text } }),
  markWatched: (id: number) =>
    api<{ ok: boolean; last_watched_post_id: number }>(`/api/posts/${id}/watched/`, { method: "POST" }),
};

export const BooksApi = {
  search: (page = 1, search?: FeedSearch) =>
    api<Paginated<Book>>(`/api/books/?${bookQuery(page, search)}`),
};

export const ShelfApi = {
  mine: () =>
    api<{ shelves: Shelf[]; pending_returns: Shelf[]; lent_out_count?: number }>(
      "/api/shelf/"
    ),
  addIsbn: (isbn: string) => api<Shelf>("/api/shelf/isbn/", { method: "POST", body: { isbn } }),
  addManual: (body: {
    isbn: string;
    title: string;
    authors?: string;
    publisher?: string;
    publish_date?: string;
    cover_url?: string;
    info_url?: string;
  }) => api<Shelf>("/api/shelf/manual/", { method: "POST", body }),
  remove: (id: number) => api(`/api/shelf/${id}/`, { method: "DELETE" }),
  returnBook: (id: number) => api(`/api/shelf/${id}/return/`, { method: "POST" }),
  confirmReturn: (id: number) => api(`/api/shelf/${id}/confirm-return/`, { method: "POST" }),
  readerAge: (id: number, min_readers_age: number, max_readers_age: number) =>
    api<Book>(`/api/shelf/${id}/reader-age/`, { method: "POST", body: { min_readers_age, max_readers_age } }),
};

export const SlipApi = {
  list: () => api<{ borrowed: Shelf[]; lent: Shelf[]; loan_days: number }>("/api/slips/"),
};

export const BrowseApi = {
  list: () =>
    api<{ others: Shelf[]; others_grouped: BookBrowseGroup[]; my_owned: Shelf[] }>(
      "/api/browse/"
    ),
  user: (id: number) =>
    api<{
      user: User;
      is_own: boolean;
      shelves: Shelf[];
      /** @deprecated physical presence is a single shelves list */
      borrowed?: Shelf[];
      borrowed_request_targets?: Record<string, number>;
    }>(`/api/users/${id}/shelf/`),
  book: (id: number) =>
    api<{ book: Book; owners: User[]; holders: Shelf[]; posts: Post[] }>(
      `/api/books/${id}/`
    ),
};

export const CopyApi = {
  history: (copyId: number) =>
    api<{
      copy: BookCopyDetail;
      holders: Shelf[];
      events: CopyEvent[];
      queue: QueueEntry[];
      queue_length: number;
      my_queue_position: number | null;
      is_lent_out: boolean;
    }>(`/api/copies/${copyId}/history/`),
  queue: (copyId: number) =>
    api<{
      queue: QueueEntry[];
      my_queue_position: number | null;
      is_lent_out: boolean;
    }>(`/api/copies/${copyId}/queue/`),
  joinQueue: (copyId: number) =>
    api<{ ok: boolean; position: number; queue: QueueEntry[] }>(
      `/api/copies/${copyId}/queue/join/`,
      { method: "POST" }
    ),
  leaveQueue: (copyId: number) =>
    api<{ ok: boolean; queue: QueueEntry[] }>(`/api/copies/${copyId}/queue/leave/`, {
      method: "POST",
    }),
};

export const QueueApi = {
  mine: () =>
    api<{
      results: {
        id: number;
        copy_id: number;
        book_title: string;
        owner_id: number;
        owner_username: string;
        status: string;
        position: number;
        created_at: string;
      }[];
    }>("/api/queue/mine/"),
};

export const ExchangeApi = {
  list: () =>
    api<{ pending_in: Exchange[]; pending_out: Exchange[]; history: Exchange[] }>("/api/exchanges/"),
  create: (target_shelf_id: number, offer_shelf_id?: number | null) =>
    api<{ created: Exchange[]; errors: string[] }>("/api/exchanges/create/", {
      method: "POST",
      body: { target_shelf_id, offer_shelf_id: offer_shelf_id || null },
    }),
  accept: (id: number) => api(`/api/exchanges/${id}/accept/`, { method: "POST" }),
  reject: (id: number) => api(`/api/exchanges/${id}/reject/`, { method: "POST" }),
  cancel: (id: number) => api(`/api/exchanges/${id}/cancel/`, { method: "POST" }),
};

export const HandoffApi = {
  confirmGive: (id: number) => api(`/api/handoffs/${id}/give/`, { method: "POST" }),
  confirmReceive: (id: number) => api(`/api/handoffs/${id}/receive/`, { method: "POST" }),
  cancel: (id: number) => api(`/api/handoffs/${id}/cancel/`, { method: "POST" }),
};

export const MsgApi = {
  partners: () => api<User[]>("/api/messages/partners/"),
  thread: (id: number) =>
    api<{
      partner: User;
      messages: Message[];
      pending_in: Exchange[];
      pending_out: Exchange[];
      pending_returns: Shelf[];
      handoffs: LoanHandoff[];
    }>(`/api/messages/${id}/`),
  send: (id: number, body: string) =>
    api<Message>(`/api/messages/${id}/`, { method: "POST", body: { body } }),
};

export type AppNotification = {
  id: number;
  kind: string;
  body: string;
  created_at: string;
  read_at: string | null;
  is_unread: boolean;
  chat_partner_id: number;
  chat_partner_username: string;
  exchange_request_id: number | null;
  /** Рядок полиці позичальника — кнопка «Підтвердити» для власника. */
  confirm_return_shelf_id?: number | null;
  sender?: User;
};

export const NotifApi = {
  list: () =>
    api<{ unread_count: number; results: AppNotification[] }>("/api/notifications/"),
  unreadCount: () => api<{ unread_count: number }>("/api/notifications/unread-count/"),
  markRead: (ids?: number[]) =>
    api<{ marked: number; unread_count: number }>("/api/notifications/mark-read/", {
      method: "POST",
      body: ids ? { ids } : {},
    }),
};
