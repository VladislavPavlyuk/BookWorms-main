import { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, BrowseApi } from "../../src/api";
import { colors } from "../../src/theme";
import type { Book, Post, Shelf } from "../../src/types";

export default function BookScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [book, setBook] = useState<Book | null>(null);
  const [holders, setHolders] = useState<Shelf[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);

  useEffect(() => {
    BrowseApi.book(Number(id))
      .then((d) => {
        setBook(d.book);
        setHolders(d.holders);
        setPosts(d.posts);
      })
      .catch((e) => Alert.alert("Книга", e instanceof ApiError ? e.message : String(e)));
  }, [id]);

  if (!book) return null;

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.paper }} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.title}>{book.title}</Text>
      <Text style={styles.meta}>{book.authors} · ISBN {book.isbn}</Text>
      <Text style={styles.meta}>{book.reader_age_summary}</Text>
      <Text style={styles.h}>На полицях</Text>
      {holders.map((s) => (
        <Pressable key={s.id} onPress={() => router.push(`/user/${s.user.id}`)}>
          <Text style={styles.row}>
            {s.user.username}
            {s.borrowed_from ? ` (позичено у ${s.borrowed_from.username})` : ""}
            {s.due_date ? ` до ${s.due_date}` : ""}
          </Text>
        </Pressable>
      ))}
      <Text style={styles.h}>Пости</Text>
      {posts.map((p) => (
        <View key={p.id} style={styles.card}>
          <Text style={styles.ptitle}>{p.title}</Text>
          <Text style={styles.meta}>{p.author.username}</Text>
          <Text style={{ color: colors.ink, marginTop: 6 }}>{p.text}</Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: 22, fontWeight: "800", color: colors.ink },
  meta: { color: colors.muted, marginTop: 4 },
  h: { marginTop: 20, fontWeight: "800", color: colors.ink },
  row: { color: colors.ink, paddingVertical: 8, borderBottomWidth: 1, borderColor: colors.line },
  card: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white, padding: 12, marginTop: 8 },
  ptitle: { fontWeight: "700", color: colors.ink },
});
