/**
 * Auth used to strip non-ASCII — product now requires Cyrillic in every field.
 * Kept as identity helpers so call sites can stay stable / be removed gradually.
 */
export function latinAuthOnly(text: string): string {
  return text;
}
