import { useCallback, useState } from "react";
import {
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, FeedApi } from "../../src/api";
import { colors } from "../../src/theme";
import type { Post } from "../../src/types";

export default function Feed() {
  const router = useRouter();
  const [posts, setPosts] = useState<Post[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [filter, setFilter] = useState<"all" | "my">("all");
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = async (p = 1, mode: "all" | "my" = filter, append = false) => {
    const data = await FeedApi.list(p, mode === "my" ? "my" : undefined);
    setPosts((prev) => (append ? [...prev, ...data.results] : data.results));
    setPage(p);
    setHasMore(Boolean(data.next));
  };

  useFocusEffect(
    useCallback(() => {
      load(1, filter).catch((e) =>
        Alert.alert("Стрічка", e instanceof ApiError ? e.message : String(e))
      );
    }, [filter])
  );

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

  return (
    <View style={{ flex: 1, backgroundColor: colors.paper }}>
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
      <FlatList
        data={posts}
        keyExtractor={(p) => String(p.id)}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={async () => {
              setRefreshing(true);
              await load(1, filter);
              setRefreshing(false);
            }}
          />
        }
        onEndReached={async () => {
          if (!hasMore || loadingMore) return;
          setLoadingMore(true);
          try {
            await load(page + 1, filter, true);
          } finally {
            setLoadingMore(false);
          }
        }}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <Pressable style={styles.card} onPress={() => router.push(`/post/${item.id}`)}>
            <Pressable onPress={() => router.push(`/user/${item.author.id}`)}>
              <Text style={styles.meta}>
                {item.author.username}
                {item.book ? ` · ${item.book.title}` : ""}
              </Text>
            </Pressable>
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.body} numberOfLines={4}>
              {item.text}
            </Text>
            <Pressable onPress={() => like(item.id)}>
              <Text style={[styles.like, item.liked_by_me && { color: colors.stamp }]}>
                ♥ {item.likes_count} · коментарі {item.comments_count}
              </Text>
            </Pressable>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 12, paddingTop: 8 },
  filters: { flexDirection: "row", gap: 8 },
  chip: { color: colors.muted, fontWeight: "700", paddingHorizontal: 10, paddingVertical: 6 },
  chipOn: { color: colors.ink, backgroundColor: colors.paperDark },
  newBtn: { backgroundColor: colors.ink, paddingHorizontal: 14, paddingVertical: 8 },
  newBtnText: { color: colors.white, fontWeight: "700" },
  card: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white, padding: 14, marginBottom: 12 },
  meta: { color: colors.muted, fontSize: 12, marginBottom: 4 },
  title: { color: colors.ink, fontSize: 18, fontWeight: "700" },
  body: { color: colors.ink, marginTop: 6, lineHeight: 20 },
  like: { marginTop: 10, color: colors.muted, fontWeight: "600" },
});
