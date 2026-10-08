import * as SecureStore from "expo-secure-store";
import { DEFAULT_API } from "./theme";
import {
  BookCopyDetail,
  Book,
  BookBrowseGroup,
  Comment,
  CopyEvent,
  Exchange,
  LibrarySnapshot,
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
  /** When true, body is FormData — do not set JSON Content-Type. */
  formData?: boolean;
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
  const isForm = opts.formData || (typeof FormData !== "undefined" && opts.body instanceof FormData);
  if (opts.body !== undefined && !isForm) {
    headers["Content-Type"] = "application/json; charset=utf-8";
  }

  const exec = (t: string | null) => {
    const h = { ...headers };
    if (t) h.Authorization = `Bearer ${t}`;
    else delete h.Authorization;
    let body: BodyInit | undefined;
    if (opts.body !== undefined) {
      body = isForm ? (opts.body as FormData) : JSON.stringify(opts.body);
    }
    return fetch(`${base}${path}`, {
      method: opts.method || "GET",
      headers: h,
      body,
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
  checkAvailability: (username: string, email: string) => {
    const q = new URLSearchParams();
    if (username) q.set("username", username);
    if (email) q.set("email", email);
    return api<{
      username: string;
      email: string;
      username_available: boolean | null;
      email_available: boolean | null;
      username_taken: boolean;
      email_taken: boolean;
      suggestions: string[];
      message_uk: string;
    }>(`/api/auth/check-availability/?${q.toString()}`, { auth: false });
  },
  me: () => api<User>("/api/auth/me/"),
  updateMe: (
    body:
      | {
          username?: string;
          biography?: string;
          age?: number | null;
          place?: string;
          preferred_subjects?: string[];
        }
      | FormData
  ) =>
    api<User>("/api/auth/me/", {
      method: "PATCH",
      body,
      formData: body instanceof FormData,
    }),
  listSubprofiles: () =>
    api<import("./types").UserSubProfile[]>("/api/auth/me/subprofiles/"),
  createSubprofile: (body: {
    name: string;
    age?: number | null;
    place?: string;
    preferred_subjects?: string[];
  }) =>
    api<import("./types").UserSubProfile>("/api/auth/me/subprofiles/", {
      method: "POST",
      body,
    }),
  updateSubprofile: (
    id: number,
    body: {
      name?: string;
      age?: number | null;
      place?: string;
      preferred_subjects?: string[];
    }
  ) =>
    api<import("./types").UserSubProfile>(`/api/auth/me/subprofiles/${id}/`, {
      method: "PATCH",
      body,
    }),
  deleteSubprofile: (id: number) =>
    api<void>(`/api/auth/me/subprofiles/${id}/`, { method: "DELETE" }),
};

export const ContactApi = {
  config: () =>
    api<{
      access_key: string;
      endpoint: string;
      max_screenshots: number;
      max_file_bytes: number;
      message_max: number;
      to_hint: string;
    }>("/api/contact/config/", { auth: false }),
};

export type FeedSearch = {
  q?: string;
  isbn?: string;
  authors?: string;
  publisher?: string;
  /** @deprecated use year_from / year_to */
  publish_date?: string;
  year_from?: string;
  year_to?: string;
  language?: string;
  /** Theme/Genre — exact match in Book.subjects */
  subject?: string;
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
  subjects: () =>
    api<{ subjects: string[] }>("/api/books/subjects/", { auth: false }),
};

export const ShelfApi = {
  mine: () =>
    api<{
      shelves: Shelf[];
      pending_returns: Shelf[];
      lent_out_count?: number;
      price_total_uah?: string;
      is_shared_library?: boolean;
      shared_member_count?: number;
      shared_library_name?: string;
      i_am_library_admin?: boolean;
    }>("/api/shelf/"),
  refreshPrice: (bookId: number) =>
    api<{ ok: boolean; price_eval: import("./types").BookPriceEval | null }>(
      `/api/books/${bookId}/price/refresh/`,
      { method: "POST" }
    ),
  refreshMetadata: (bookId: number) =>
    api<{
      ok: boolean;
      detail?: string;
      search_source?: string;
      book?: import("./types").Book;
      search_log?: { provider: string; label: string; status: string; detail?: string }[];
    }>(`/api/books/${bookId}/metadata/refresh/`, { method: "POST" }),
  addIsbn: (isbn: string, confirmExtra = false) =>
    api<
      | (Shelf & {
          search_log?: { provider: string; label: string; status: string; detail?: string }[];
          search_source?: string;
        })
      | {
          needs_confirmation?: boolean;
          pending_approval?: boolean;
          existing_count?: number;
          title?: string;
          isbn?: string;
          detail?: string;
          action_id?: number;
          chat_partner_id?: number;
          search_log?: { provider: string; label: string; status: string; detail?: string }[];
          search_source?: string;
        }
    >("/api/shelf/isbn/", {
      method: "POST",
      body: { isbn, confirm_extra: confirmExtra },
    }),
  addManual: (body: {
    isbn?: string;
    title?: string;
    authors?: string;
    publisher?: string;
    publish_date?: string;
    cover_url?: string;
    info_url?: string;
    cover_text?: string;
    confirm_extra?: boolean;
    photos?: { uri: string; name?: string; type?: string }[];
  }) => {
    const photos = body.photos || [];
    if (!photos.length) {
      const { photos: _p, ...json } = body;
      return api<Shelf>("/api/shelf/manual/", { method: "POST", body: json });
    }
    const fd = new FormData();
    if (body.isbn) fd.append("isbn", body.isbn);
    if (body.title) fd.append("title", body.title);
    if (body.authors) fd.append("authors", body.authors);
    if (body.publisher) fd.append("publisher", body.publisher);
    if (body.publish_date) fd.append("publish_date", body.publish_date);
    if (body.cover_url) fd.append("cover_url", body.cover_url);
    if (body.info_url) fd.append("info_url", body.info_url);
    if (body.cover_text) fd.append("cover_text", body.cover_text);
    if (body.confirm_extra) fd.append("confirm_extra", "true");
    photos.forEach((p, i) => {
      fd.append("photos", {
        uri: p.uri,
        name: p.name || `book_${i}.jpg`,
        type: p.type || "image/jpeg",
      } as unknown as Blob);
    });
    return api<Shelf>("/api/shelf/manual/", { method: "POST", body: fd, formData: true });
  },
  updateManual: (
    shelfId: number,
    body: {
      isbn?: string;
      title?: string;
      authors?: string;
      publisher?: string;
      publish_date?: string;
      cover_url?: string;
      info_url?: string;
      cover_text?: string;
      delete_photo_ids?: number[];
      photos?: { uri: string; name?: string; type?: string }[];
    }
  ) => {
    const photos = body.photos || [];
    const deletes = body.delete_photo_ids || [];
    // Always multipart/POST — avoids PATCH quirks and empty JSON edge cases.
    const fd = new FormData();
    if (body.isbn != null) fd.append("isbn", body.isbn);
    if (body.title != null) fd.append("title", body.title);
    if (body.authors != null) fd.append("authors", body.authors);
    if (body.publisher != null) fd.append("publisher", body.publisher);
    if (body.publish_date != null) fd.append("publish_date", body.publish_date);
    if (body.cover_url) fd.append("cover_url", body.cover_url);
    if (body.info_url) fd.append("info_url", body.info_url);
    if (body.cover_text != null) fd.append("cover_text", body.cover_text);
    deletes.forEach((id) => fd.append("delete_photo_ids", String(id)));
    photos.forEach((p, i) => {
      fd.append("photos", {
        uri: p.uri,
        name: p.name || `book_${i}.jpg`,
        type: p.type || "image/jpeg",
      } as unknown as Blob);
    });
    return api<Shelf>(`/api/shelf/${shelfId}/manual/`, { method: "POST", body: fd, formData: true });
  },
  recognizeCover: (
    photos:
      | { uri: string; name?: string; type?: string }
      | { uri: string; name?: string; type?: string }[]
  ) => {
    const list = Array.isArray(photos) ? photos : [photos];
    const fd = new FormData();
    list.forEach((photo, i) => {
      fd.append("photos", {
        uri: photo.uri,
        name: photo.name || `cover_${i + 1}.jpg`,
        type: photo.type || "image/jpeg",
      } as unknown as Blob);
    });
    return api<{
      title: string;
      authors: string;
      isbn: string;
      publisher: string;
      publish_date: string;
      source?: string;
      raw_text?: string;
      cover_text?: string;
      isbn_missing?: boolean;
      note?: string;
      photos_scanned?: number;
      photos_ok?: number;
      best_photo_index?: number;
    }>("/api/shelf/recognize-cover/", { method: "POST", body: fd, formData: true });
  },
  remove: (id: number) =>
    api<
      | void
      | {
          pending_approval?: boolean;
          action_id?: number;
          chat_partner_id?: number;
          detail?: string;
        }
    >(`/api/shelf/${id}/`, { method: "DELETE" }),
  returnBook: (id: number) => api(`/api/shelf/${id}/return/`, { method: "POST" }),
  confirmReturn: (id: number, qr_payload?: string) =>
    api(`/api/shelf/${id}/confirm-return/`, {
      method: "POST",
      body: qr_payload ? { qr_payload } : {},
    }),
  readerAge: (id: number, min_readers_age: number, max_readers_age: number) =>
    api<Book>(`/api/shelf/${id}/reader-age/`, { method: "POST", body: { min_readers_age, max_readers_age } }),
  updateListing: (
    id: number,
    body: {
      is_fee_sharing?: boolean;
      is_hidden?: boolean;
      is_for_rent?: boolean;
      is_for_exchange?: boolean;
      is_free_of_deposit?: boolean;
      sale_gift?: string;
      sale_price?: string | number | null;
      rent_price_per_day?: string | number | null;
    }
  ) =>
    api<
      | Shelf
      | {
          pending_approval?: boolean;
          action_id?: number;
          chat_partner_id?: number;
          detail?: string;
        }
    >(`/api/shelf/${id}/listing/`, { method: "POST", body }),
  bulk: (body: {
    action: "delete" | "listing";
    shelf_ids: number[];
    is_fee_sharing?: boolean;
    is_hidden?: boolean;
    is_for_rent?: boolean;
    is_for_exchange?: boolean;
    is_free_of_deposit?: boolean;
    sale_gift?: string;
    sale_price?: string | number | null;
    rent_price_per_day?: string | number | null;
  }) =>
    api<{
      ok?: boolean;
      pending_approval?: boolean;
      action_id?: number;
      chat_partner_id?: number;
      detail?: string;
      removed?: number;
      updated?: number;
      blocked?: number[];
      count?: number;
    }>("/api/shelf/bulk/", { method: "POST", body }),
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
  ensureQr: (copyId: number) =>
    api<{ copy: BookCopyDetail; qr: Record<string, unknown> }>(
      `/api/copies/${copyId}/qr/ensure/`,
      { method: "POST", body: {} }
    ),
  attachQr: (copyId: number, qr_payload: string) =>
    api<{ ok: boolean; copy: BookCopyDetail }>(`/api/copies/${copyId}/qr/attach/`, {
      method: "POST",
      body: { qr_payload },
    }),
  rotateQr: (copyId: number) =>
    api<{ ok: boolean; copy: BookCopyDetail }>(`/api/copies/${copyId}/qr/rotate/`, {
      method: "POST",
      body: {},
    }),
  resolveQr: (qr_payload: string, opts?: { handoff_id?: number; action?: "give" | "receive" }) =>
    api<{
      ok?: boolean;
      action?: string;
      handoff_id?: number;
      copy?: BookCopyDetail;
      active_handoff?: LoanHandoff | null;
    }>("/api/copies/qr/resolve/", {
      method: "POST",
      body: {
        qr_payload,
        ...(opts?.handoff_id ? { handoff_id: opts.handoff_id } : {}),
        ...(opts?.action ? { action: opts.action } : {}),
      },
    }),
  printLabels: (opts?: { pages?: number }) => {
    const q: string[] = [];
    if (opts?.pages && opts.pages > 1) q.push(`pages=${opts.pages}`);
    const qs = q.length ? `?${q.join("&")}` : "";
    return api<{
      qr_mm: number;
      label_w_mm?: number;
      label_h_mm?: number;
      cols: number;
      rows: number;
      slots_per_page: number;
      pages: ({
        copy_id: number | null;
        title: string;
        payload: string;
        data_uri: string;
        attached: boolean;
      } | null)[][];
      labels: {
        copy_id: number | null;
        title: string;
        payload: string;
        data_uri: string;
        attached: boolean;
      }[];
    }>(`/api/copies/qr/print-labels/${qs}`);
  },
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

export const LibraryApi = {
  mine: () => api<LibrarySnapshot>("/api/library/"),
  generateMergeCode: () =>
    api<{
      code: string;
      expires_at: string;
      seconds_left: number;
      ttl_seconds: number;
    }>("/api/library/merge-code/generate/", { method: "POST", body: {} }),
  redeemMergeCode: (code: string) =>
    api<{
      ok?: boolean;
      library_id?: number;
      name?: string;
      awaiting_admin_isbn?: boolean;
      invite_id?: number;
      overlap?: unknown[];
      detail?: string;
    }>("/api/library/merge-code/redeem/", {
      method: "POST",
      body: { code },
    }),
  acceptInvite: (inviteId: number, isbn_counts: Record<string, number> = {}) =>
    api<{
      ok?: boolean;
      library_id?: number;
      awaiting_admin_isbn?: boolean;
      needs_isbn_counts?: boolean;
      overlap?: unknown[];
      detail?: string;
      invite_id?: number;
    }>(`/api/library/invite/${inviteId}/accept/`, {
      method: "POST",
      body: { isbn_counts },
    }),
  confirmMergeIsbn: (inviteId: number, isbn_counts: Record<string, number>) =>
    api<{
      ok?: boolean;
      library_id?: number;
      needs_isbn_counts?: boolean;
      overlap?: unknown[];
      detail?: string;
    }>(`/api/library/invite/${inviteId}/confirm-isbn/`, {
      method: "POST",
      body: { isbn_counts },
    }),
  rejectInvite: (inviteId: number) =>
    api<{ ok: boolean }>(`/api/library/invite/${inviteId}/reject/`, { method: "POST" }),
  cancelInvite: (inviteId: number) =>
    api<{ ok: boolean }>(`/api/library/invite/${inviteId}/cancel/`, { method: "POST" }),
  resolveAction: (actionId: number, approve: boolean) =>
    api<{ ok: boolean }>(`/api/library/actions/${actionId}/resolve/`, {
      method: "POST",
      body: { approve },
    }),
  splitLeave: (copy_ids: number[]) =>
    api<{ pending_approval?: boolean; action_id?: number; ok?: boolean }>("/api/library/split/", {
      method: "POST",
      body: { copy_ids },
    }),
  startElection: (reason = "Зміна адміністратора") =>
    api<Record<string, unknown>>("/api/library/election/start/", {
      method: "POST",
      body: { reason },
    }),
  voteElection: (electionId: number, candidate_id: number) =>
    api<Record<string, unknown>>(`/api/library/election/${electionId}/vote/`, {
      method: "POST",
      body: { candidate_id },
    }),
  finalizeElection: (electionId: number) =>
    api<Record<string, unknown>>(`/api/library/election/${electionId}/finalize/`, {
      method: "POST",
      body: {},
    }),
  cancelElection: (electionId: number) =>
    api<{ ok: boolean }>(`/api/library/election/${electionId}/cancel/`, { method: "POST" }),
};

export const ExchangeApi = {
  list: () =>
    api<{ pending_in: Exchange[]; pending_out: Exchange[]; history: Exchange[] }>("/api/exchanges/"),
  create: (
    target_shelf_id: number,
    offer_shelf_id?: number | null,
    proposed_due_date?: string | null,
    offer_open?: boolean
  ) =>
    api<{ created: Exchange[]; errors: string[] }>("/api/exchanges/create/", {
      method: "POST",
      body: {
        target_shelf_id,
        offer_shelf_id: offer_shelf_id || null,
        offer_open: !!offer_open && !offer_shelf_id,
        ...(proposed_due_date ? { proposed_due_date } : {}),
      },
    }),
  offerable: (id: number) => api<Shelf[]>(`/api/exchanges/${id}/offerable/`),
  pickOffer: (id: number, offer_shelf_id: number) =>
    api<Exchange>(`/api/exchanges/${id}/pick-offer/`, {
      method: "POST",
      body: { offer_shelf_id },
    }),
  accept: (id: number, due_date?: string | null) =>
    api(`/api/exchanges/${id}/accept/`, {
      method: "POST",
      body: due_date ? { due_date } : {},
    }),
  proposeDue: (id: number, due_date: string) =>
    api<Exchange>(`/api/exchanges/${id}/propose-due/`, {
      method: "POST",
      body: { due_date },
    }),
  confirmDue: (id: number) =>
    api<Exchange>(`/api/exchanges/${id}/confirm-due/`, { method: "POST", body: {} }),
  reject: (id: number) => api(`/api/exchanges/${id}/reject/`, { method: "POST" }),
  cancel: (id: number) => api(`/api/exchanges/${id}/cancel/`, { method: "POST" }),
};

export const HandoffApi = {
  confirmGive: (id: number, qr_payload?: string | null) =>
    api(`/api/handoffs/${id}/give/`, {
      method: "POST",
      body: qr_payload ? { qr_payload } : {},
    }),
  confirmReceive: (id: number, qr_payload?: string | null) =>
    api(`/api/handoffs/${id}/receive/`, {
      method: "POST",
      body: qr_payload ? { qr_payload } : {},
    }),
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
      library_invites_in?: {
        id: number;
        library_name: string;
        from_username: string;
        message: string;
        overlap: {
          isbn: string;
          title: string;
          combined: number;
          target_count: number;
          source_count: number;
        }[];
      }[];
      library_invites_out?: {
        id: number;
        library_name: string;
        to_username: string;
        message: string;
        status?: string;
        overlap?: {
          isbn: string;
          title: string;
          combined: number;
          target_count: number;
          source_count: number;
        }[];
      }[];
      library_actions_in?: {
        id: number;
        title: string;
        isbn: string;
        existing_count: number;
        count?: number;
        action_type?: string;
        action_type_label?: string;
        initiator_username: string;
        library_name: string;
      }[];
      library_actions_out?: {
        id: number;
        title: string;
        isbn: string;
        existing_count: number;
        count?: number;
        action_type?: string;
        action_type_label?: string;
        initiator_username: string;
        library_name: string;
      }[];
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
