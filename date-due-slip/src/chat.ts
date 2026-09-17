import type { Exchange, User } from "./types";

/** Partner for chat from an exchange row (desktop: Чат on each request). */
export function exchangeChatPartnerId(e: Exchange, meId: number | undefined): number | null {
  if (!meId) return null;
  if (e.requester.id === meId) return e.shelf_owner.id;
  if (e.shelf_owner.id === meId) return e.requester.id;
  return null;
}

export function formatMsgTime(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yyyy = d.getFullYear();
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    return `${dd}.${mm}.${yyyy} ${hh}:${mi}`;
  } catch {
    return "";
  }
}

export function otherPartners(all: User[], currentId: number): User[] {
  return all.filter((p) => p.id !== currentId);
}
