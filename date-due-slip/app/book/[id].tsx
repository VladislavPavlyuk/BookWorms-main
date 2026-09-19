import { useEffect, useState } from "react";
import { Alert, Image, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, BrowseApi } from "../../src/api";
import { RequestModal } from "../../src/RequestModal";
import { useAuth } from "../../src/auth";
import { colors } from "../../src/theme";
import type { Book, Post, Shelf } from "../../src/types";

export default function BookScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [book, setBook] = useState<Book | null>(null);
  const [holders, setHolders] = useState<Shelf[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [myOwned, setMyOwned] = useState<Shelf[]>([]);
  const [target, setTarget] = useState<Shelf | null>(null);

  const load = async () => {
    const [d, browse] = await Promise.all([BrowseApi.book(Number(id)), BrowseApi.list()]);
    setBook(d.book);
    setHolders(d.holders);
    setPosts(d.posts);
    setMyOwned(browse.my_owned);
  };

  useEffect(() => {
    load().catch((e) => Alert.alert("Книга", e instanceof ApiError ? e.message : String(e)));
  }, [id]);

  if (!book) return null;

  const onMyShelf = holders.some((h) => h.user.id === user?.id);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.screen }} contentContainerStyle={{ padding: 16 }}>
      {!!book.cover_url && (
        <Image source={{ uri: book.cover_url }} style={styles.cover} resizeMode="contain" />
      )}
      <Text style={styles.title}>{book.title}</Text>
      <Text style={styles.meta}>{book.authors || "—"}</Text>
      <Text style={styles.meta}>ISBN {book.isbn}</Text>
      <Text style={styles.meta}>
        {book.publisher}
        {book.publish_date ? ` · ${book.publish_date}` : ""}
      </Text>
      <Text style={styles.meta}>Вік: {book.reader_age_summary}</Text>
      {!!book.info_url && (
        <Pressable onPress={() => Linking.openURL(book.info_url)}>
          <Text style={styles.link}>Open Library</Text>
        </Pressable>
      )}

      {onMyShelf && (
        <Pressable
          style={styles.btn}
          onPress={() => router.push({ pathname: "/post/new", params: { book_id: String(book.id) } })}
        >
          <Text style={styles.btnText}>Написати пост про цю книгу</Text>
        </Pressable>
      )}

      <Text style={styles.h}>На полицях</Text>
      {holders.map((s) => (
        <View key={s.id} style={styles.card}>
          <Pressable onPress={() => router.push(`/user/${s.user.id}`)}>
            <Text style={styles.row}>
              {s.user.username}
              {s.borrowed_from ? ` (позичено у ${s.borrowed_from.username})` : " · власна"}
              {s.due_date ? ` до ${s.due_date}` : ""}
            </Text>
          </Pressable>
          {user && s.user.id !== user.id && !s.borrowed_from && (
            <Pressable onPress={() => setTarget(s)}>
              <Text style={styles.act}>Позичити / обмін</Text>
            </Pressable>
          )}
        </View>
      ))}

      <Text style={styles.h}>Пости</Text>
      {posts.length === 0 ? <Text style={styles.meta}>немає</Text> : null}
      {posts.map((p) => (
        <Pressable key={p.id} style={styles.card} onPress={() => router.push(`/post/${p.id}`)}>
          <Text style={styles.ptitle}>{p.title}</Text>
          <Text style={styles.meta}>
            {p.author.username} · ♥ {p.likes_count}
          </Text>
          <Text style={{ color: colors.ink, marginTop: 6 }} numberOfLines={3}>
            {p.text}
          </Text>
        </Pressable>
      ))}

      <RequestModal target={target} myOwned={myOwned} onClose={() => setTarget(null)} onDone={load} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  cover: { width: "100%", height: 200, marginBottom: 12, backgroundColor: colors.paperDark },
  title: { fontSize: 22, fontWeight: "800", color: colors.ink },
  meta: { color: colors.muted, marginTop: 4 },
  link: { color: colors.stamp, fontWeight: "700", marginTop: 8 },
  btn: { backgroundColor: colors.ink, padding: 12, marginTop: 16 },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700" },
  h: { marginTop: 24, fontWeight: "800", color: colors.ink, marginBottom: 8 },
  card: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white, padding: 12, marginBottom: 8 },
  row: { color: colors.ink, fontWeight: "600" },
  act: { color: colors.stamp, fontWeight: "800", marginTop: 8 },
  ptitle: { fontWeight: "700", color: colors.ink },
});
