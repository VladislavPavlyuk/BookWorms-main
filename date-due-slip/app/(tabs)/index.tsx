import { useCallback, useMemo, useState } from "react";
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
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, BooksApi, FeedApi, type FeedSearch } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { colors } from "../../src/theme";
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

  const search = useMemo<FeedSearch>(
    () => ({ q: appliedQ, ...appliedAdv }),
    [appliedQ, appliedAdv]
  );
  const searching = hasSearch(search);

  const loadPosts = async (p = 1, mode: "all" | "my" = filter, append = false) => {
    const data = await FeedApi.list(p, mode === "my" ? "my" : undefined);
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
      if (searching) {
        loadBooks(1, search).catch((e) =>
          Alert.alert("Пошук книг", e instanceof ApiError ? e.message : String(e))
        );
      } else {
        setBooks([]);
        loadPosts(1, filter).catch((e) =>
          Alert.alert("Стрічка", e instanceof ApiError ? e.message : String(e))
        );
      }
    }, [filter, search, searching])
  );

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
      Alert.alert("Лайк", e instanceof ApiError ? e.message : String(e));
    }
  };

  const setAdvField = (key: keyof FeedSearch, value: string) =>
    setAdv((prev) => ({ ...prev, [key]: value }));

  return (
    <View style={{ flex: 1, backgroundColor: colors.screen }}>
      <View style={styles.stickyChrome}>
        <View style={styles.searchRow}>
          <TextInput
            style={styles.searchInput}
            placeholder="Пошук книги за назвою…"
            placeholderTextColor={colors.muted}
            value={q}
            onChangeText={setQ}
            onSubmitEditing={runSearch}
            returnKeyType="search"
          />
          <Pressable style={styles.searchBtn} onPress={runSearch}>
            <Text style={styles.searchBtnText}>Знайти</Text>
          </Pressable>
        </View>
        <View style={styles.advRow}>
          <Pressable style={styles.advBtn} onPress={() => setAdvOpen(true)}>
            <Text style={styles.advBtnText}>Advanced search</Text>
          </Pressable>
          {searching && (
            <Pressable onPress={clearSearch}>
              <Text style={styles.clear}>Скинути</Text>
            </Pressable>
          )}
        </View>
      </View>

      {!searching && (
        <View style={styles.top}>
          <View style={styles.filters}>
            <Pressable onPress={() => setFilter("all")}>
              <Text style={[styles.chip, filter === "all" && styles.chipOn]}>Усі</Text>
            </Pressable>
            <Pressable onPress={() => setFilter("my")}>
              <Text style={[styles.chip, filter === "my" && styles.chipOn]}>Мої</Text>
            </Pressable>
          </View>
          <Pressable style={styles.newBtn} onPress={() => router.push("/post/new")}>
            <Text style={styles.newBtnText}>+ Пост</Text>
          </Pressable>
        </View>
      )}

      {searching ? (
        <FlatList
          style={{ flex: 1 }}
          data={books}
          keyExtractor={(b) => String(b.id)}
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
          contentContainerStyle={{ paddingBottom: 40 }}
          ListHeaderComponent={
            <Text style={[styles.section, { paddingHorizontal: 16, paddingTop: 12 }]}>
              Книги · {books.length}{booksHasMore ? "+" : ""}
            </Text>
          }
          ListEmptyComponent={<Text style={styles.empty}>Книг не знайдено.</Text>}
          renderItem={({ item }) => (
            <Pressable style={styles.card} onPress={() => router.push(`/book/${item.id}`)}>
              <BookCover uri={item.cover_url} size="full" bleed={0} style={styles.coverFull} />
              <View style={styles.cardPad}>
                <Text style={styles.title}>{item.title}</Text>
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
          )}
        />
      ) : (
        <FlatList
          style={{ flex: 1 }}
          data={posts}
          keyExtractor={(p) => String(p.id)}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={async () => {
                setRefreshing(true);
                await loadPosts(1, filter);
                setRefreshing(false);
              }}
            />
          }
          onEndReached={async () => {
            if (!hasMore || loadingMore) return;
            setLoadingMore(true);
            try {
              await loadPosts(page + 1, filter, true);
            } finally {
              setLoadingMore(false);
            }
          }}
          contentContainerStyle={{ paddingBottom: 40 }}
          ListEmptyComponent={<Text style={styles.empty}>Стрічка порожня.</Text>}
          renderItem={({ item }) => (
            <Pressable style={styles.card} onPress={() => router.push(`/post/${item.id}`)}>
              <View style={styles.cardPad}>
                <Pressable onPress={() => router.push(`/user/${item.author.id}`)}>
                  <Text style={styles.meta}>{item.author.username}</Text>
                </Pressable>
              </View>
              {item.book ? (
                <Pressable onPress={() => router.push(`/book/${item.book!.id}`)}>
                  <BookCover uri={item.book.cover_url} size="full" bleed={0} style={styles.coverFull} />
                  <Text style={[styles.bookLink, styles.cardPad]}>{item.book.title}</Text>
                </Pressable>
              ) : null}
              <View style={styles.cardPad}>
                <Text style={styles.title}>{item.title}</Text>
                <Text style={styles.body} numberOfLines={4}>
                  {item.text}
                </Text>
                <Pressable onPress={() => like(item.id)}>
                  <Text style={[styles.like, item.liked_by_me && { color: colors.stamp }]}>
                    ♥ {item.likes_count} · коментарі {item.comments_count}
                  </Text>
                </Pressable>
              </View>
            </Pressable>
          )}
        />
      )}

      <Modal visible={advOpen} animationType="slide" onRequestClose={() => setAdvOpen(false)}>
        <View style={styles.modal}>
          <Text style={styles.modalTitle}>Advanced search · книги</Text>
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
    </View>
  );
}

const styles = StyleSheet.create({
  stickyChrome: {
    backgroundColor: colors.paperDark,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    paddingBottom: 8,
    zIndex: 10,
    elevation: 4,
    shadowColor: "#000",
    shadowOpacity: 0.12,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
  },
  searchRow: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 12,
    paddingTop: 10,
    alignItems: "center",
  },
  searchInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    color: colors.ink,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
  },
  searchBtn: { backgroundColor: colors.ink, paddingHorizontal: 14, paddingVertical: 11 },
  searchBtnText: { color: colors.white, fontWeight: "700" },
  advRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 12,
    paddingTop: 8,
  },
  advBtn: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paperDark,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  advBtnText: { color: colors.ink, fontWeight: "700", fontSize: 13 },
  clear: { color: colors.stamp, fontWeight: "700" },
  top: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingTop: 10,
  },
  filters: { flexDirection: "row", gap: 8 },
  chip: { color: colors.muted, fontWeight: "700", paddingHorizontal: 10, paddingVertical: 6 },
  chipOn: { color: colors.ink, backgroundColor: colors.paperDark },
  newBtn: { backgroundColor: colors.ink, paddingHorizontal: 14, paddingVertical: 8 },
  newBtnText: { color: colors.white, fontWeight: "700" },
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
  coverFull: { maxHeight: undefined },
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
