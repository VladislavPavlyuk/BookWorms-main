import { memo, useCallback, useEffect, useRef, useState } from "react";
import {
  Image,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
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
import { colors, fs, s } from "./theme";

/**
 * Uncontrolled search field.
 * Controlled TextInput + parent re-renders (unread poll / layout) drops Cyrillic on Android IME.
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

  // external clear / reset only — never while user is typing
  useEffect(() => {
    if (initialQ === lastExternal.current) return;
    lastExternal.current = initialQ;
    setNonce((n) => n + 1);
  }, [initialQ]);

  return (
    <TextInput
      key={`search-${nonce}`}
      style={styles.searchInput}
      placeholder="Назва…"
      placeholderTextColor={colors.muted}
      defaultValue={initialQ}
      onChangeText={onQueryChange}
      onSubmitEditing={onSubmit}
      returnKeyType="search"
      autoCorrect={false}
      spellCheck={false}
      autoCapitalize="none"
      autoComplete="off"
      textContentType="none"
      importantForAutofill="no"
      // Android: visible-password disables suggestion strip that eats Cyrillic IME
      keyboardType={Platform.OS === "android" ? "visible-password" : "default"}
      underlineColorAndroid="transparent"
    />
  );
});

const CHROME_IDLE_MS = 2000;

/**
 * Спільний хром: [‹] logo | search | ⧩ filter | 🔔 | ☰
 * While typing: hide filter/notif/burger so search expands; restore after 2s idle.
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
  const [chromeHidden, setChromeHidden] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chromeIdleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typingRef = useRef(false);

  const inTabs = segments[0] === "(tabs)";
  const showBack = !inTabs;

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (chromeIdleRef.current) clearTimeout(chromeIdleRef.current);
    };
  }, []);

  // sync from context only when not typing (Скинути etc.)
  useEffect(() => {
    if (typingRef.current) return;
    typedQ.current = search.q || "";
    setDisplayQ(search.q || "");
    setAdv({
      isbn: search.isbn || "",
      authors: search.authors || "",
      publisher: search.publisher || "",
      publish_date: search.publish_date || "",
      age_min: search.age_min || "",
      age_max: search.age_max || "",
    });
  }, [search]);

  const scheduleChromeRestore = useCallback(() => {
    setChromeHidden(true);
    if (chromeIdleRef.current) clearTimeout(chromeIdleRef.current);
    chromeIdleRef.current = setTimeout(() => {
      setChromeHidden(false);
      chromeIdleRef.current = null;
    }, CHROME_IDLE_MS);
  }, []);

  const applySearch = useCallback(
    (next: FeedSearch) => {
      typingRef.current = false;
      setSearch(next);
      if (!inTabs) router.push("/(tabs)" as never);
    },
    [inTabs, router, setSearch]
  );

  const onQueryChange = useCallback(
    (t: string) => {
      typingRef.current = true;
      typedQ.current = t;
      scheduleChromeRestore();
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const trimmed = typedQ.current.trim();
        if (Array.from(trimmed).length >= 3) {
          applySearch({
            q: trimmed,
            isbn: adv.isbn,
            authors: adv.authors,
            publisher: adv.publisher,
            publish_date: adv.publish_date,
            age_min: adv.age_min,
            age_max: adv.age_max,
          });
        }
      }, 1000);
    },
    [adv, applySearch, scheduleChromeRestore]
  );

  const runSearch = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    applySearch({
      q: typedQ.current.trim(),
      isbn: adv.isbn,
      authors: adv.authors,
      publisher: adv.publisher,
      publish_date: adv.publish_date,
      age_min: adv.age_min,
      age_max: adv.age_max,
    });
  }, [adv, applySearch]);

  const applyAdvanced = () => {
    setAdvOpen(false);
    runSearch();
  };

  const setAdvField = (key: keyof FeedSearch, value: string) =>
    setAdv((prev) => ({ ...prev, [key]: value }));

  const resetAll = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (chromeIdleRef.current) clearTimeout(chromeIdleRef.current);
    typingRef.current = false;
    typedQ.current = "";
    setDisplayQ("");
    setChromeHidden(false);
    setAdv(EMPTY_FEED_SEARCH);
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

        <SearchField
          initialQ={displayQ}
          onQueryChange={onQueryChange}
          onSubmit={runSearch}
        />

        {!chromeHidden ? (
          <>
            <Pressable
              style={styles.advBtn}
              onPress={() => setAdvOpen(true)}
              accessibilityLabel="Фільтр"
            >
              <FilterGlyph color={colors.ink} size={s(18)} />
            </Pressable>
            <HeaderActions />
          </>
        ) : null}
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
              <View key={key} style={styles.field}>
                <Text style={styles.label}>{label}</Text>
                <TextInput
                  style={styles.modalInput}
                  placeholderTextColor={colors.muted}
                  value={adv[key] || ""}
                  onChangeText={(t) => setAdvField(key, t)}
                  keyboardType={key.startsWith("age_") ? "number-pad" : "default"}
                  autoCapitalize="none"
                  autoCorrect={false}
                  spellCheck={false}
                  underlineColorAndroid="transparent"
                />
              </View>
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
    paddingHorizontal: s(8),
    paddingVertical: s(7),
    fontSize: fs(16),
    height: s(36),
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
