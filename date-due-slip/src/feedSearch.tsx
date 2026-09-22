import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { FeedSearch } from "./api";

export const EMPTY_FEED_SEARCH: FeedSearch = {
  q: "",
  isbn: "",
  authors: "",
  publisher: "",
  publish_date: "",
  age_min: "",
  age_max: "",
};

export function hasFeedSearch(s: FeedSearch) {
  return Object.values(s).some((v) => (v || "").trim());
}

type FeedSearchCtx = {
  search: FeedSearch;
  setSearch: (s: FeedSearch) => void;
  clearSearch: () => void;
};

const Ctx = createContext<FeedSearchCtx | null>(null);

/** In-memory search (UTF-8 / кирилиця). Не через URL params — expo-router їх псує. */
export function FeedSearchProvider({ children }: { children: ReactNode }) {
  const [search, setSearchState] = useState<FeedSearch>(EMPTY_FEED_SEARCH);

  const setSearch = useCallback((s: FeedSearch) => {
    setSearchState({
      q: (s.q || "").trim(),
      isbn: (s.isbn || "").trim(),
      authors: (s.authors || "").trim(),
      publisher: (s.publisher || "").trim(),
      publish_date: (s.publish_date || "").trim(),
      age_min: (s.age_min || "").trim(),
      age_max: (s.age_max || "").trim(),
    });
  }, []);

  const clearSearch = useCallback(() => setSearchState(EMPTY_FEED_SEARCH), []);

  const value = useMemo(
    () => ({ search, setSearch, clearSearch }),
    [search, setSearch, clearSearch]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFeedSearch() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFeedSearch outside FeedSearchProvider");
  return ctx;
}
