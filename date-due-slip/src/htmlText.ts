/** Strip ISBN catalog HTML to readable plain text for RN Text. */
const BLOCK = /<\/?(?:p|div|h[1-6]|li|tr|blockquote|br|hr)(?:\s[^>]*)?\/?>/gi;
const TAG = /<\/?[a-zA-Z][^>]*>/g;
const ENTITY: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
};

export function htmlToPlain(input?: string | null, maxLen?: number): string {
  if (!input) return "";
  let s = String(input)
    .replace(BLOCK, "\n")
    .replace(TAG, "")
    .replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (_, name: string) => {
      const key = name.toLowerCase();
      if (ENTITY[key]) return ENTITY[key];
      if (key.startsWith("#x")) {
        const n = parseInt(key.slice(2), 16);
        return Number.isFinite(n) ? String.fromCodePoint(n) : "";
      }
      if (key.startsWith("#")) {
        const n = parseInt(key.slice(1), 10);
        return Number.isFinite(n) ? String.fromCodePoint(n) : "";
      }
      return "";
    })
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if (maxLen != null && s.length > maxLen) {
    s = s.slice(0, maxLen).replace(/\s+\S*$/, "") + "…";
  }
  return s;
}
