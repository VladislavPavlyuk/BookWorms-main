import { useCallback, useMemo, useRef, useState } from "react";
import {
  Alert,
  FlatList,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  ViewToken,
  useWindowDimensions,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ApiError, AuthApi, BooksApi, FeedApi, type FeedSearch } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { HeaderActions } from "../../src/BurgerMenu";
import { colors } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
import type { Book, Post } from "../../src/types";

const EMPTY_ADV: FeedSearch = {
  isbn: "",
  authors: "",
  publisher: "",
  publish_date: "",
  age_min: "",
  age_max: "",
};

function hasSearch(s: FeedSearch) {
  return Object.values(s).some((v) => (v || "").trim());
}

export default function Feed() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { width: winW, height: winH } = useWindowDimensions();
  const landscape = winW > winH;
  // chrome ≈ safe top + top bar + search row + filters
  const chromeH = insets.top + (landscape ? 88 : 96);
  const pageH = Math.max(200, winH - chromeH);
  const lastMarked = useRef<number | null>(null);
  const skipResumeRef = useRef(false);
  const resumeFromId = useRef<number | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [books, setBooks] = useState<Book[]>([]);
  const [page, setPage] = useState(1);
  const [bookPage, setBookPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [booksHasMore, setBooksHasMore] = useState(false);
  const [filter, setFilter] = useState<"all" | "my">("all");
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [q, setQ] = useState("");
  const [appliedQ, setAppliedQ] = useState("");
  const [adv, setAdv] = useState<FeedSearch>(EMPTY_ADV);
  const [appliedAdv, setAppliedAdv] = useState<FeedSearch>(EMPTY_ADV);
  const [advOpen, setAdvOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const search = useMemo<FeedSearch>(
    () => ({ q: appliedQ, ...appliedAdv }),
    [appliedQ, appliedAdv]
  );
  const searching = hasSearch(search);

  const loadPosts = async (
    p = 1,
    mode: "all" | "my" = filter,
    append = false,
    fromId: number | null = resumeFromId.current
  ) => {
    const data = await FeedApi.list(p, mode === "my" ? "my" : undefined, fromId);
    setPosts((prev) => (append ? [...prev, ...data.results] : data.results));
    setPage(p);
    setHasMore(Boolean(data.next));
  };

  const loadBooks = async (p = 1, s: FeedSearch = search, append = false) => {
    const data = await BooksApi.search(p, s);
    setBooks((prev) => (append ? [...prev, ...data.results] : data.results));
    setBookPage(p);
    setBooksHasMore(Boolean(data.next));
  };

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        if (searching) {
          try {
            await loadBooks(1, search);
          } catch (e) {
            Alert.alert("Пошук книг", e instanceof ApiError ? e.message : String(e));
          }
          return;
        }
        setBooks([]);
        let watched: number | null = null;
        try {
          const me = await AuthApi.me();
          watched = me.last_watched_post_id ?? null;
        } catch {
          watched = null;
        }
        if (cancelled) return;
        const fromId = skipResumeRef.current ? null : watched;
        skipResumeRef.current = false;
        resumeFromId.current = fromId;
        try {
          await loadPosts(1, filter, false, fromId);
        } catch (e) {
          Alert.alert("Головна", e instanceof ApiError ? e.message : String(e));
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [filter, search, searching])
  );

  const onViewableItemsChanged = useRef(
    ({ viewableItems }: { viewableItems: ViewToken[] }) => {
      const top = viewableItems.find((v) => v.isViewable && v.item);
      if (!top?.item) return;
      const id = (top.item as Post).id;
      if (lastMarked.current === id) return;
      lastMarked.current = id;
      FeedApi.markWatched(id).catch(() => {});
    }
  ).current;

  const viewabilityConfig = useRef({
    itemVisiblePercentThreshold: 55,
    minimumViewTime: 400,
  }).current;

  const runSearch = () => {
    setAppliedQ(q.trim());
    setAppliedAdv({ ...adv });
  };

  const clearSearch = () => {
    setQ("");
    setAppliedQ("");
    setAdv(EMPTY_ADV);
    setAppliedAdv(EMPTY_ADV);
    setAdvOpen(false);
    setBooks([]);
  };

  const like = async (id: number) => {
    try {
      const r = await FeedApi.like(id);
      setPosts((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, liked_by_me: r.liked, likes_count: r.likes_count } : p
        )
      );
    } catch (e) {
      Alert.alert("Вподобайка", e instanceof ApiError ? e.message : String(e));
    }
  };

  const setAdvField = (key: keyof FeedSearch, value: string) =>
    setAdv((prev) => ({ ...prev, [key]: value }));

  return (
    <View style={{ flex: 1, backgroundColor: colors.screen }}>
      <View style={[styles.stickyChrome, { paddingTop: insets.top }]}>
        <View style={styles.searchRow}>
          <TextInput
            style={styles.searchInput}
            placeholder="Назва…"
            placeholderTextColor={colors.muted}
            value={q}
            onChangeText={setQ}
            onSubmitEditing={runSearch}
            returnKeyType="search"
          />
          <Pressable style={styles.searchBtn} onPress={runSearch}>
            <Text style={styles.searchBtnText}>Шукати</Text>
          </Pressable>
          <Pressable
            style={styles.advBtn}
            onPress={() => setAdvOpen(true)}
            accessibilityLabel="Рітельніше"
          >
            <Text style={styles.advBtnText} numberOfLines={1}>
              Рітельніше
            </Text>
          </Pressable>
          <HeaderActions />
        </View>
        <View style={styles.advRow}>
          {searching && (
            <Pressable onPress={clearSearch}>
              <Text style={styles.clear}>Скинути</Text>
            </Pressable>
          )}
          {!searching && (
            <View style={styles.filters}>
              <Pressable onPress={() => setFilter("all")}>
                <Text style={[styles.chip, filter === "all" && styles.chipOn]}>Усі</Text>
              </Pressable>
              <Pressable onPress={() => setFilter("my")}>
                <Text style={[styles.chip, filter === "my" && styles.chipOn]}>Мої</Text>
              </Pressable>
            </View>
          )}
        </View>
      </View>

      {searching ? (
        <FlatList
          key={`books-${landscape ? "h" : "v"}`}
          style={{ flex: 1 }}
          data={books}
          keyExtractor={(b) => String(b.id)}
          horizontal={landscape}
          pagingEnabled={landscape}
          showsHorizontalScrollIndicator={landscape}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={async () => {
                setRefreshing(true);
                await loadBooks(1, search);
                setRefreshing(false);
              }}
            />
          }
          onEndReached={async () => {
            if (!booksHasMore || loadingMore) return;
            setLoadingMore(true);
            try {
              await loadBooks(bookPage + 1, search, true);
            } finally {
              setLoadingMore(false);
            }
          }}
          contentContainerStyle={
            landscape
              ? { paddingVertical: 8 }
              : { paddingBottom: 40 }
          }
          ListHeaderComponent={
            landscape ? null : (
              <Text style={[styles.section, { paddingHorizontal: 16, paddingTop: 12 }]}>
                Книги · {books.length}
                {booksHasMore ? "+" : ""}
              </Text>
            )
          }
          ListEmptyComponent={<Text style={styles.empty}>Книг не знайдено.</Text>}
          renderItem={({ item }) => (
            <View style={[styles.card, landscape && { width: winW, height: pageH }]}>
              <Pressable onPress={() => router.push(`/book/${item.id}`)}>
                <BookCover uri={item.cover_url} size="full" bleed={0} />
                <View style={styles.cardPad}>
                  <Text style={styles.title} numberOfLines={landscape ? 2 : undefined}>
                    {item.title}
                  </Text>
                  {!!item.authors && <Text style={styles.meta}>{item.authors}</Text>}
                  <Text style={styles.meta}>ISBN {item.isbn}</Text>
                  {(item.publisher || item.publish_date) && (
                    <Text style={styles.meta}>
                      {[item.publisher, item.publish_date].filter(Boolean).join(", ")}
                    </Text>
                  )}
                  <Text style={styles.meta}>Вік: {item.reader_age_summary}</Text>
                </View>
              </Pressable>
            </View>
          )}
        />
      ) : (
        <FlatList
          key={`posts-${landscape ? "h" : "v"}`}
          style={{ flex: 1 }}
          data={posts}
          keyExtractor={(p) => String(p.id)}
          horizontal={landscape}
          pagingEnabled={landscape}
          showsHorizontalScrollIndicator={landscape}
          onViewableItemsChanged={onViewableItemsChanged}
          viewabilityConfig={viewabilityConfig}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={async () => {
                setRefreshing(true);
                skipResumeRef.current = true;
                resumeFromId.current = null;
                try {
                  await loadPosts(1, filter, false, null);
                } finally {
                  setRefreshing(false);
                }
              }}
            />
          }
          onEndReached={async () => {
            if (!hasMore || loadingMore) return;
            setLoadingMore(true);
            try {
              await loadPosts(page + 1, filter, true, resumeFromId.current);
            } finally {
              setLoadingMore(false);
            }
          }}
          contentContainerStyle={
            landscape ? { paddingVertical: 8 } : { paddingBottom: 40 }
          }
          ListEmptyComponent={<Text style={styles.empty}>Стрічка порожня.</Text>}
          renderItem={({ item }) => (
            <Pressable
              style={[styles.card, landscape && styles.cardLandscape, landscape && { width: winW, height: pageH }]}
              onPress={() => router.push(`/post/${item.id}`)}
            >
              <ScrollView
                style={landscape ? { flex: 1 } : undefined}
                contentContainerStyle={landscape ? styles.cardLandscapeInner : undefined}
                nestedScrollEnabled
              >
                <View style={styles.cardPad}>
                  <UserNameLink user={item.author} style={styles.meta} />
                </View>
                {item.book ? (
                  <Pressable onPress={() => router.push(`/book/${item.book!.id}`)}>
                    <BookCover uri={item.book.cover_url} size="full" bleed={0} />
                    <Text style={[styles.bookLink, styles.cardPad]}>{item.book.title}</Text>
                  </Pressable>
                ) : null}
                <View style={styles.cardPad}>
                  <Text style={styles.title}>{item.title}</Text>
                  <Text style={styles.body} numberOfLines={landscape ? 6 : 4}>
                    {item.text}
                  </Text>
                  <Pressable onPress={() => like(item.id)}>
                    <Text style={[styles.like, item.liked_by_me && { color: colors.stamp }]}>
                      ♥ {item.likes_count} · коментарі {item.comments_count}
                    </Text>
                  </Pressable>
                </View>
              </ScrollView>
            </Pressable>
          )}
        />
      )}

      <Modal visible={advOpen} animationType="slide" onRequestClose={() => setAdvOpen(false)}>
        <View style={styles.modal}>
          <Text style={styles.modalTitle}>Рітельніше · книги</Text>
          <ScrollView contentContainerStyle={{ paddingBottom: 24 }}>
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
                  style={styles.input}
                  placeholderTextColor={colors.muted}
                  value={adv[key] || ""}
                  onChangeText={(t) => setAdvField(key, t)}
                  keyboardType={key.startsWith("age_") ? "number-pad" : "default"}
                />
              </View>
            ))}
          </ScrollView>
          <View style={styles.modalActions}>
            <Pressable
              style={styles.searchBtn}
              onPress={() => {
                setAdvOpen(false);
                runSearch();
              }}
            >
              <Text style={styles.searchBtnText}>Застосувати</Text>
            </Pressable>
            <Pressable onPress={() => setAdvOpen(false)}>
              <Text style={styles.clear}>Закрити</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      {!searching && (
        <>
          <Pressable
            style={({ pressed }) => [
              styles.fab,
              { bottom: Math.max(16, insets.bottom + 12), right: 16 },
              pressed && styles.fabPressed,
            ]}
            onPress={() => setCreateOpen(true)}
            accessibilityRole="button"
            accessibilityLabel="Створити пост"
          >
            <Text style={styles.fabPlus}>+</Text>
          </Pressable>

          <Modal visible={createOpen} transparent animationType="fade" onRequestClose={() => setCreateOpen(false)}>
            <View style={styles.createScrim}>
              <Pressable style={StyleSheet.absoluteFill} onPress={() => setCreateOpen(false)} />
              <View style={styles.createSheet}>
                <Text style={styles.createTitle}>Створити пост</Text>
                <Pressable
                  style={styles.createOpt}
                  onPress={() => {
                    setCreateOpen(false);
                    router.push({ pathname: "/post/new", params: { mode: "event" } });
                  }}
                >
                  <Text style={styles.createOptTitle}>Подія</Text>
                  <Text style={styles.createOptSub}>Анонс або новина без книги</Text>
                </Pressable>
                <Pressable
                  style={styles.createOpt}
                  onPress={() => {
                    setCreateOpen(false);
                    router.push({ pathname: "/post/new", params: { mode: "feedback" } });
                  }}
                >
                  <Text style={styles.createOptTitle}>Відгук про прочитану книгу</Text>
                  <Text style={styles.createOptSub}>Книга з вашої полиці</Text>
                </Pressable>
                <Pressable onPress={() => setCreateOpen(false)}>
                  <Text style={styles.createCancel}>Скасувати</Text>
                </Pressable>
              </View>
            </View>
          </Modal>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  stickyChrome: {
    backgroundColor: colors.paperDark,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    paddingBottom: 8,
    zIndex: 20,
    elevation: 6,
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 5,
    shadowOffset: { width: 0, height: 2 },
  },
  searchRow: {
    flexDirection: "row",
    flexWrap: "nowrap",
    gap: 4,
    paddingHorizontal: 8,
    paddingTop: 6,
    alignItems: "center",
  },
  searchInput: {
    flex: 1,
    minWidth: 0,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    color: colors.ink,
    paddingHorizontal: 8,
    paddingVertical: 7,
    fontSize: 14,
    height: 36,
  },
  searchBtn: {
    backgroundColor: colors.ink,
    paddingHorizontal: 8,
    height: 36,
    justifyContent: "center",
    flexShrink: 0,
  },
  searchBtnText: { color: colors.white, fontWeight: "700", fontSize: 11 },
  advRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 10,
    paddingHorizontal: 12,
    paddingTop: 6,
  },
  advBtn: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    paddingHorizontal: 5,
    height: 36,
    justifyContent: "center",
    flexShrink: 1,
    maxWidth: 96,
  },
  advBtnText: { color: colors.ink, fontWeight: "700", fontSize: 10 },
  clear: { color: colors.stamp, fontWeight: "700" },
  filters: { flexDirection: "row", gap: 6 },
  chip: { color: colors.muted, fontWeight: "700", paddingHorizontal: 10, paddingVertical: 6 },
  chipOn: { color: colors.ink, backgroundColor: colors.white },
  fab: {
    position: "absolute",
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.fab,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 40,
    elevation: 10,
    shadowColor: colors.fab,
    shadowOpacity: 0.45,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    borderWidth: 2,
    borderColor: "#14A3A8",
  },
  fabPressed: {
    backgroundColor: colors.fabPressed,
  },
  fabPlus: {
    color: colors.white,
    fontSize: 36,
    fontWeight: "300",
    lineHeight: 40,
    includeFontPadding: false,
    marginTop: -2,
  },
  createScrim: {
    flex: 1,
    backgroundColor: "rgba(42, 31, 20, 0.45)",
    justifyContent: "flex-end",
  },
  createSheet: {
    backgroundColor: colors.paper,
    borderTopWidth: 1,
    borderColor: colors.line,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 28,
    zIndex: 2,
  },
  createTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: colors.ink,
    marginBottom: 12,
  },
  createOpt: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 14,
    marginBottom: 8,
  },
  createOptTitle: { color: colors.ink, fontWeight: "700", fontSize: 16 },
  createOptSub: { color: colors.muted, marginTop: 4, fontSize: 13 },
  createCancel: {
    color: colors.stamp,
    fontWeight: "700",
    textAlign: "center",
    marginTop: 10,
    padding: 8,
  },
  section: { color: colors.ink, fontWeight: "800", marginBottom: 10, fontSize: 16 },
  card: {
    borderWidth: 0,
    borderBottomWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 0,
    marginBottom: 0,
    overflow: "hidden",
  },
  cardLandscape: {
    borderBottomWidth: 0,
    borderRightWidth: 1,
    height: "100%",
  },
  cardLandscapeInner: {
    paddingBottom: 16,
    flexGrow: 1,
  },
  coverFull: {},
  cardPad: { paddingHorizontal: 16, paddingBottom: 14 },
  bookLink: {
    color: colors.stamp,
    fontWeight: "700",
    fontSize: 13,
    marginTop: 8,
  },
  meta: { color: colors.muted, fontSize: 12, marginBottom: 4 },
  title: {
    color: colors.ink,
    fontSize: 17,
    fontWeight: "700",
    marginTop: 12,
    marginBottom: 4,
  },
  body: { color: colors.ink, marginTop: 6, lineHeight: 20 },
  like: {
    marginTop: 10,
    color: colors.muted,
    fontWeight: "600",
  },
  empty: { textAlign: "center", color: colors.muted, marginTop: 24 },
  modal: { flex: 1, backgroundColor: colors.paper, paddingTop: 48, paddingHorizontal: 16 },
  modalTitle: { fontSize: 20, fontWeight: "800", color: colors.ink, marginBottom: 12 },
  field: { marginBottom: 10 },
  label: { color: colors.muted, fontSize: 12, marginBottom: 4, fontWeight: "600" },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: 8,
    fontSize: 16,
  },
  modalActions: { flexDirection: "row", alignItems: "center", gap: 16, paddingVertical: 16 },
});
