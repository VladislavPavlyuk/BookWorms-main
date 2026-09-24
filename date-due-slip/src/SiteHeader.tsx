import { memo, useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import {
  Image,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { GestureHandlerRootView, ScrollView } from "react-native-gesture-handler";
import { useRouter, useSegments } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { FeedSearch } from "./api";
import { HeaderActions } from "./BurgerMenu";
import { EMPTY_FEED_SEARCH, useFeedSearch } from "./feedSearch";
import { CloseGlyph, FilterGlyph } from "./HeaderGlyphs";
import { CyrillicTextInput } from "./CyrillicTextInput";
import { colors, fs, s } from "./theme";

const CHROME_IDLE_MS = 2000;

type ChromeApi = {
  onTyping: () => void;
  reset: () => void;
};

/**
 * Uncontrolled search — remounting / parent setState during IME composition
 * drops Cyrillic on Android (esp. emulator). Never remount while focused;
 * chrome hide lives in a sibling so typing does not re-render this input.
 */
const SearchField = memo(function SearchField({
  initialQ,
  onQueryChange,
  onSubmit,
}: {
  initialQ: string;
  onQueryChange: (q: string) => void;
  onSubmit: () => void;
}) {
  const [nonce, setNonce] = useState(0);
  const lastExternal = useRef(initialQ);
  const focusedRef = useRef(false);

  useEffect(() => {
    if (initialQ === lastExternal.current) return;
    if (focusedRef.current) {
      // Autosearch updated context to the same typed string — absorb, do not remount.
      lastExternal.current = initialQ;
      return;
    }
    lastExternal.current = initialQ;
    setNonce((n) => n + 1);
  }, [initialQ]);

  return (
    <CyrillicTextInput
      key={`search-${nonce}`}
      style={styles.searchInput}
      placeholder="Назва…"
      placeholderTextColor={colors.muted}
      defaultValue={initialQ}
      onChangeText={onQueryChange}
      onSubmitEditing={onSubmit}
      onFocus={() => {
        focusedRef.current = true;
      }}
      onBlur={() => {
        focusedRef.current = false;
      }}
      returnKeyType="search"
      autoCapitalize="none"
      keyboardType="default"
      showSoftInputOnFocus
    />
  );
});

/** Filter + bell + burger — own state so search IME is not interrupted. */
const HeaderTrailing = memo(function HeaderTrailing({
  apiRef,
  onOpenFilter,
}: {
  apiRef: MutableRefObject<ChromeApi | null>;
  onOpenFilter: () => void;
}) {
  const [hidden, setHidden] = useState(false);
  const idleRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    apiRef.current = {
      onTyping: () => {
        setHidden(true);
        if (idleRef.current) clearTimeout(idleRef.current);
        idleRef.current = setTimeout(() => {
          setHidden(false);
          idleRef.current = null;
        }, CHROME_IDLE_MS);
      },
      reset: () => {
        if (idleRef.current) clearTimeout(idleRef.current);
        idleRef.current = null;
        setHidden(false);
      },
    };
    return () => {
      if (idleRef.current) clearTimeout(idleRef.current);
      apiRef.current = null;
    };
  }, [apiRef]);

  if (hidden) return null;

  return (
    <>
      <Pressable style={styles.advBtn} onPress={onOpenFilter} accessibilityLabel="Фільтр">
        <FilterGlyph color={colors.ink} size={s(18)} />
      </Pressable>
      <HeaderActions />
    </>
  );
});

/**
 * Спільний хром: [‹] logo | search | ⧩ filter | 🔔 | ☰
 */
export function SiteHeader() {
  const router = useRouter();
  const segments = useSegments();
  const insets = useSafeAreaInsets();
  const { height: winH } = useWindowDimensions();
  const { search, setSearch, clearSearch } = useFeedSearch();

  const typedQ = useRef(search.q || "");
  const [displayQ, setDisplayQ] = useState(search.q || "");
  const [adv, setAdv] = useState<FeedSearch>({
    isbn: search.isbn || "",
    authors: search.authors || "",
    publisher: search.publisher || "",
    publish_date: search.publish_date || "",
    age_min: search.age_min || "",
    age_max: search.age_max || "",
  });
  const [advOpen, setAdvOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typingRef = useRef(false);
  const chromeApi = useRef<ChromeApi | null>(null);
  const advDraft = useRef(adv);

  const inTabs = segments[0] === "(tabs)";
  const showBack = !inTabs;

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // sync from context only when not typing (Скинути etc.)
  useEffect(() => {
    if (typingRef.current) return;
    typedQ.current = search.q || "";
    setDisplayQ(search.q || "");
    const next = {
      isbn: search.isbn || "",
      authors: search.authors || "",
      publisher: search.publisher || "",
      publish_date: search.publish_date || "",
      age_min: search.age_min || "",
      age_max: search.age_max || "",
    };
    setAdv(next);
    advDraft.current = next;
  }, [search]);

  const applySearch = useCallback(
    (next: FeedSearch) => {
      // Keep typingRef true while the user is still in the field — avoids remount/IME kill.
      setSearch(next);
      if (!inTabs) router.push("/(tabs)" as never);
    },
    [inTabs, router, setSearch]
  );

  const onQueryChange = useCallback(
    (t: string) => {
      typingRef.current = true;
      typedQ.current = t;
      chromeApi.current?.onTyping();
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const trimmed = typedQ.current.trim();
        if (Array.from(trimmed).length >= 3) {
          const a = advDraft.current;
          applySearch({
            q: trimmed,
            isbn: a.isbn,
            authors: a.authors,
            publisher: a.publisher,
            publish_date: a.publish_date,
            age_min: a.age_min,
            age_max: a.age_max,
          });
        }
      }, 1000);
    },
    [applySearch]
  );

  const runSearch = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    typingRef.current = false;
    const a = advDraft.current;
    applySearch({
      q: typedQ.current.trim(),
      isbn: a.isbn,
      authors: a.authors,
      publisher: a.publisher,
      publish_date: a.publish_date,
      age_min: a.age_min,
      age_max: a.age_max,
    });
  }, [applySearch]);

  const applyAdvanced = () => {
    setAdvOpen(false);
    typingRef.current = false;
    runSearch();
  };

  const setAdvField = (key: keyof FeedSearch, value: string) => {
    advDraft.current = { ...advDraft.current, [key]: value };
    setAdv(advDraft.current);
  };

  const resetAll = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    typingRef.current = false;
    typedQ.current = "";
    setDisplayQ("");
    chromeApi.current?.reset();
    setAdv(EMPTY_FEED_SEARCH);
    advDraft.current = EMPTY_FEED_SEARCH;
    clearSearch();
  };

  return (
    <View style={[styles.wrap, { paddingTop: insets.top }]}>
      <View style={styles.row}>
        {showBack ? (
          <Pressable
            onPress={() => router.back()}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Назад"
            hitSlop={6}
          >
            <Text style={styles.backChevron}>‹</Text>
          </Pressable>
        ) : null}

        <Pressable
          onPress={() => {
            resetAll();
            router.push("/(tabs)" as never);
          }}
          style={styles.logoHit}
          accessibilityRole="button"
          accessibilityLabel="Реченець — головна"
        >
          <Image
            source={require("../assets/logo-transparent.png")}
            style={styles.logo}
            resizeMode="contain"
          />
        </Pressable>

        <SearchField initialQ={displayQ} onQueryChange={onQueryChange} onSubmit={runSearch} />

        <HeaderTrailing apiRef={chromeApi} onOpenFilter={() => setAdvOpen(true)} />
      </View>

      <Modal
        visible={advOpen}
        animationType="slide"
        presentationStyle="fullScreen"
        onRequestClose={() => setAdvOpen(false)}
        statusBarTranslucent
      >
        <GestureHandlerRootView
          style={[
            styles.modalRoot,
            {
              height: winH,
              paddingTop: insets.top + 12,
              paddingBottom: Math.max(insets.bottom, 12),
            },
          ]}
        >
          <View style={styles.modalHead}>
            <Text style={styles.modalTitle}>Фільтр · книги</Text>
            <Pressable onPress={() => setAdvOpen(false)} hitSlop={8} style={styles.modalClose}>
              <CloseGlyph color={colors.ink} size={18} />
            </Pressable>
          </View>
          <ScrollView
            style={styles.modalScroll}
            contentContainerStyle={styles.modalScrollContent}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="on-drag"
            showsVerticalScrollIndicator
            bounces
            nestedScrollEnabled
          >
            {(
              [
                ["isbn", "ISBN"],
                ["authors", "Автори"],
                ["publisher", "Видавець"],
                ["publish_date", "Дата видання"],
                ["age_min", "Вік від (0–18)"],
                ["age_max", "Вік до (0–18)"],
              ] as const
            ).map(([key, label]) => (
              <AdvField
                key={`${key}-${advOpen}`}
                label={label}
                initial={adv[key] || ""}
                keyboardType={key.startsWith("age_") ? "number-pad" : "default"}
                onChange={(t) => setAdvField(key, t)}
              />
            ))}
            <View style={styles.modalActions}>
              <Pressable style={styles.searchBtnWide} onPress={applyAdvanced}>
                <Text style={styles.searchBtnText}>Застосувати</Text>
              </Pressable>
              <Pressable
                onPress={() => {
                  resetAll();
                  setAdvOpen(false);
                  if (!inTabs) router.push("/(tabs)" as never);
                }}
              >
                <Text style={styles.clear}>Скинути</Text>
              </Pressable>
              <Pressable onPress={() => setAdvOpen(false)}>
                <Text style={styles.clear}>Закрити</Text>
              </Pressable>
            </View>
          </ScrollView>
        </GestureHandlerRootView>
      </Modal>
    </View>
  );
}

/** Uncontrolled adv field — avoids Android IME drop from controlled setState. */
const AdvField = memo(function AdvField({
  label,
  initial,
  keyboardType,
  onChange,
}: {
  label: string;
  initial: string;
  keyboardType: "default" | "number-pad";
  onChange: (t: string) => void;
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <CyrillicTextInput
        style={styles.modalInput}
        placeholderTextColor={colors.muted}
        defaultValue={initial}
        onChangeText={onChange}
        keyboardType={keyboardType}
        autoCapitalize="none"
        showSoftInputOnFocus
      />
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.paperDark,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    paddingBottom: s(8),
    zIndex: 30,
    elevation: 8,
  },
  row: {
    flexDirection: "row",
    flexWrap: "nowrap",
    alignItems: "center",
    gap: s(4),
    paddingHorizontal: s(8),
    paddingTop: s(6),
  },
  backBtn: {
    width: s(28),
    height: s(36),
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  backChevron: {
    color: colors.ink,
    fontSize: fs(28),
    fontWeight: "300",
    lineHeight: s(32),
    marginTop: -2,
  },
  logoHit: { flexShrink: 0, marginRight: 2 },
  logo: { width: s(48), height: s(48) },
  searchInput: {
    flex: 1,
    minWidth: 0,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    color: colors.ink,
    paddingHorizontal: s(14),
    paddingVertical: s(7),
    fontSize: fs(16),
    height: s(36),
    borderRadius: 999,
  },
  searchBtnWide: {
    backgroundColor: colors.ink,
    paddingHorizontal: s(14),
    paddingVertical: s(10),
  },
  searchBtnText: { color: colors.white, fontWeight: "700", fontSize: fs(14) },
  advBtn: {
    borderWidth: 0,
    backgroundColor: "transparent",
    width: s(36),
    height: s(36),
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  modalRoot: {
    backgroundColor: colors.paper,
    paddingHorizontal: s(16),
    width: "100%",
  },
  modalHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: s(12),
    flexShrink: 0,
  },
  modalTitle: { fontSize: fs(20), fontWeight: "800", color: colors.ink },
  modalClose: {
    width: s(36),
    height: s(36),
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
  },
  modalScroll: {
    flex: 1,
  },
  modalScrollContent: {
    paddingBottom: s(40),
    flexGrow: 0,
  },
  field: { marginBottom: s(10) },
  label: { color: colors.muted, fontSize: fs(14), marginBottom: 4, fontWeight: "600" },
  modalInput: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: s(10),
    fontSize: fs(16),
    minHeight: s(48),
  },
  modalActions: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: s(16),
    paddingTop: s(20),
    marginTop: s(8),
  },
  clear: { color: colors.stamp, fontWeight: "700", fontSize: fs(16) },
});
