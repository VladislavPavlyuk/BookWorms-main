import { useEffect, useState } from "react";
import { getApiBase } from "./api";

/**
 * Local covers are stored as ``/media/...``. Desktop loads them same-origin;
 * RN Image needs an absolute URL on the API host the app talks to.
 */
/** Prefer stored cover, else first user/catalog photo from internal DB. */
export function bookCoverFromDb(book: {
  cover_url?: string | null;
  photo_urls?: string[] | null;
}): string | null {
  const c = (book.cover_url || "").trim();
  if (c) return c;
  const p = book.photo_urls?.[0];
  const t = (p || "").trim();
  return t || null;
}

export function resolveMediaUrl(url: string | null | undefined, apiBase: string): string {
  const u = (url || "").trim();
  if (!u) return "";
  const base = (apiBase || "").replace(/\/$/, "");
  if (!base) return u;

  // Path-only local media
  if (u.startsWith("/media/") || u.startsWith("media/")) {
    const path = u.startsWith("/") ? u : `/${u}`;
    return `${base}${path}`;
  }

  // Absolute URL that already points at /media/ — rewrite host to API base
  // (fixes docker-internal hosts like http://api:8000/media/...).
  const idx = u.indexOf("/media/");
  if (idx >= 0 && /^https?:\/\//i.test(u)) {
    return `${base}${u.slice(idx)}`;
  }

  return u;
}

/** Resolve cover/photo URI against current API base (async SecureStore). */
export function useResolvedMediaUrl(url?: string | null): string {
  const [resolved, setResolved] = useState(() => {
    const u = (url || "").trim();
    // Sync path for already-absolute non-media URLs (Open Library etc.)
    if (u && !u.includes("/media/") && /^https?:\/\//i.test(u)) return u;
    return "";
  });

  useEffect(() => {
    let cancelled = false;
    const raw = (url || "").trim();
    if (!raw) {
      setResolved("");
      return;
    }
    if (!raw.includes("/media/") && /^https?:\/\//i.test(raw)) {
      setResolved(raw);
      return;
    }
    getApiBase()
      .then((base) => {
        if (!cancelled) setResolved(resolveMediaUrl(raw, base));
      })
      .catch(() => {
        if (!cancelled) setResolved(raw);
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  return resolved;
}
