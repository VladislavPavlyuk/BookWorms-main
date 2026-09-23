import { useCallback, useRef, useState } from "react";
import {
  Alert,
  FlatList,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  ViewToken,
  useWindowDimensions,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ApiError, AuthApi, BooksApi, FeedApi, type FeedSearch } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { hasFeedSearch, useFeedSearch } from "../../src/feedSearch";
import { colors, fs, s } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
import type { Book, Post } from "../../src/types";

export default function Feed() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { width: winW, height: winH } = useWindowDimensions();
  const landscape = winW > winH;
  const chromeH = landscape ? 52 : 48;
  const pageH = Math.max(200, winH - chromeH - 56);
  const lastMarked = useRef<number | null>(null);
  const skipResumeRef = useRef(false);
  const resumeFromId = useRef<number | null>(null);

  const { search, clearSearch } = useFeedSearch();
  const searching = hasFeedSearch(search);

  const [posts, setPosts] = useState<Post[]>([]);
  const [books, setBooks] = useState<Book[]>([]);
  const [page, setPage] = useState(1);
  const [bookPage, setBookPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [booksHasMore, setBooksHasMore] = useState(false);
  const [filter, setFilter] = useState<"all" | "my">("all");
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

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

  return (
    <View style={{ flex: 1, backgroundColor: colors.screen }}>
      <View style={styles.filterBar}>
        {searching ? (
          <Pressable onPress={clearSearch}>
            <Text style={styles.clear}>Скинути пошук</Text>
          </Pressable>
        ) : (
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
            landscape ? { paddingVertical: 8 } : { paddingBottom: 40 }
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
              style={[
                styles.card,
                landscape && styles.cardLandscape,
                landscape && { width: winW, height: pageH },
              ]}
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

          <Modal
            visible={createOpen}
            transparent
            animationType="fade"
            onRequestClose={() => setCreateOpen(false)}
          >
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
  filterBar: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: s(10),
    paddingHorizontal: s(12),
    paddingVertical: s(8),
    backgroundColor: colors.paperDark,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  clear: { color: colors.stamp, fontWeight: "700", fontSize: fs(16) },
  filters: { flexDirection: "row", gap: s(6) },
  chip: {
    color: colors.muted,
    fontWeight: "700",
    paddingHorizontal: s(10),
    paddingVertical: s(8),
    fontSize: fs(16),
  },
  chipOn: { color: colors.ink, backgroundColor: colors.white },
  fab: {
    position: "absolute",
    width: s(64),
    height: s(64),
    borderRadius: s(32),
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
    fontSize: fs(36),
    fontWeight: "300",
    lineHeight: s(40),
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
    paddingHorizontal: s(20),
    paddingTop: s(16),
    paddingBottom: s(28),
    zIndex: 2,
  },
  createTitle: {
    fontSize: fs(18),
    fontWeight: "800",
    color: colors.ink,
    marginBottom: s(12),
  },
  createOpt: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: s(14),
    marginBottom: s(8),
  },
  createOptTitle: { color: colors.ink, fontWeight: "700", fontSize: fs(16) },
  createOptSub: { color: colors.muted, marginTop: 4, fontSize: fs(13) },
  createCancel: {
    color: colors.stamp,
    fontWeight: "700",
    textAlign: "center",
    marginTop: s(10),
    padding: s(8),
    fontSize: fs(16),
  },
  section: { color: colors.ink, fontWeight: "800", marginBottom: s(10), fontSize: fs(16) },
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
    paddingBottom: s(16),
    flexGrow: 1,
  },
  cardPad: { paddingHorizontal: s(16), paddingBottom: s(14) },
  bookLink: {
    color: colors.stamp,
    fontWeight: "700",
    fontSize: fs(13),
    marginTop: s(8),
  },
  meta: { color: colors.muted, fontSize: fs(12), marginBottom: 4 },
  title: {
    color: colors.ink,
    fontSize: fs(17),
    fontWeight: "700",
    marginTop: s(12),
    marginBottom: 4,
  },
  body: { color: colors.ink, marginTop: 6, lineHeight: fs(20), fontSize: fs(15) },
  like: {
    marginTop: s(10),
    color: colors.muted,
    fontWeight: "600",
    fontSize: fs(14),
  },
  empty: { textAlign: "center", color: colors.muted, marginTop: s(24), fontSize: fs(16) },
});
