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
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const data = await FeedApi.list(1);
      setPosts(data.results);
    } catch (e) {
      Alert.alert("Стрічка", e instanceof ApiError ? e.message : String(e));
    }
  };

  useFocusEffect(
    useCallback(() => {
      load();
    }, [])
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
      <Pressable style={styles.newBtn} onPress={() => router.push("/post/new")}>
        <Text style={styles.newBtnText}>+ Пост</Text>
      </Pressable>
      <FlatList
        data={posts}
        keyExtractor={(p) => String(p.id)}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />
        }
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.meta}>
              {item.author.username}
              {item.book ? ` · ${item.book.title}` : ""}
            </Text>
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.body}>{item.text}</Text>
            <Pressable onPress={() => like(item.id)}>
              <Text style={[styles.like, item.liked_by_me && { color: colors.stamp }]}>
                ♥ {item.likes_count} · коментарі {item.comments_count}
              </Text>
            </Pressable>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  newBtn: { alignSelf: "flex-end", margin: 12, backgroundColor: colors.ink, paddingHorizontal: 14, paddingVertical: 8 },
  newBtnText: { color: colors.white, fontWeight: "700" },
  card: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white, padding: 14, marginBottom: 12 },
  meta: { color: colors.muted, fontSize: 12, marginBottom: 4 },
  title: { color: colors.ink, fontSize: 18, fontWeight: "700" },
  body: { color: colors.ink, marginTop: 6, lineHeight: 20 },
  like: { marginTop: 10, color: colors.muted, fontWeight: "600" },
});
