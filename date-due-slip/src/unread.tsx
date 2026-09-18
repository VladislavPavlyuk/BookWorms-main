import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { AppState } from "react-native";
import { NotifApi, getApiBase } from "./api";
import { useAuth } from "./auth";

type Ctx = {
  unread: number;
  refresh: () => Promise<void>;
  setUnread: (n: number) => void;
  /** Остання помилка полінгу (для діагностики на фізичних девайсах). */
  pollError: string | null;
};

const C = createContext<Ctx | null>(null);

const POLL_MS = 3000;

export function UnreadProvider({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  const [unread, setUnread] = useState(0);
  const [pollError, setPollError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!user) {
      setUnread(0);
      setPollError(null);
      return;
    }
    try {
      const r = await NotifApi.unreadCount();
      setUnread(typeof r.unread_count === "number" ? r.unread_count : 0);
      setPollError(null);
    } catch (e) {
      const base = await getApiBase().catch(() => "?");
      const msg = e instanceof Error ? e.message : String(e);
      setPollError(`${msg} @ ${base}`);
      // не обнуляємо unread при тимчасовому збої — інакше бейдж «блимає» на Wi‑Fi Pixel
    }
  }, [user]);

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      setUnread(0);
      setPollError(null);
      return;
    }
    refresh();
    const interval = setInterval(refresh, POLL_MS);
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "active") refresh();
    });
    return () => {
      clearInterval(interval);
      sub.remove();
    };
  }, [user, ready, refresh]);

  return (
    <C.Provider value={{ unread, refresh, setUnread, pollError }}>
      {children}
    </C.Provider>
  );
}

export function useUnread() {
  const v = useContext(C);
  if (!v) throw new Error("useUnread");
  return v;
}
