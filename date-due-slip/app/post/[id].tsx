import { useCallback, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, FeedApi } from "../../src/api";
import { useAuth } from "../../src/auth";
import { colors, btnRadius } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
import type { Post } from "../../src/types";

export default function PostDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const router = useRouter();
  const [post, setPost] = useState<Post | null>(null);
  const [comment, setComment] = useState("");
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");

  const load = async () => {
    const p = await FeedApi.get(Number(id));
    setPost(p);
    setTitle(p.title);
    setText(p.text);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Пост", e instanceof ApiError ? e.message : String(e)));
    }, [id])
  );

  if (!post) return null;
  const mine = user?.id === post.author.id;

  const like = async () => {
    try {
      const r = await FeedApi.like(post.id);
      setPost({ ...post, liked_by_me: r.liked, likes_count: r.likes_count });
    } catch (e) {
      Alert.alert("Вподобайка", e instanceof ApiError ? e.message : String(e));
    }
  };

  const sendComment = async () => {
    try {
      await FeedApi.comment(post.id, comment.trim());
      setComment("");
      await load();
    } catch (e) {
      Alert.alert("Коментар", e instanceof ApiError ? e.message : String(e));
    }
  };

  const saveEdit = async () => {
    try {
      const p = await FeedApi.update(post.id, { title: title.trim(), text: text.trim() });
      setPost(p);
      setEditing(false);
    } catch (e) {
      Alert.alert("Редагування", e instanceof ApiError ? e.message : String(e));
    }
  };

  const remove = () => {
    Alert.alert("Видалити пост?", post.title, [
      { text: "Ні" },
      {
        text: "Так",
        style: "destructive",
        onPress: async () => {
          try {
            await FeedApi.remove(post.id);
            router.back();
          } catch (e) {
            Alert.alert("Видалення", e instanceof ApiError ? e.message : String(e));
          }
        },
      },
    ]);
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.screen }} contentContainerStyle={{ padding: 16 }}>
      <UserNameLink user={post.author} style={styles.meta} />
      {post.book && (
        <Pressable onPress={() => router.push(`/book/${post.book!.id}`)}>
          <Text style={styles.book}>{post.book.title}</Text>
        </Pressable>
      )}

      {editing ? (
        <>
          <CyrillicTextInput style={styles.input} value={title} onChangeText={setTitle} />
          <CyrillicTextInput style={[styles.input, { minHeight: 120 }]} multiline value={text} onChangeText={setText} />
          <Pressable style={styles.btn} onPress={saveEdit}>
            <Text style={styles.btnText}>Зберегти</Text>
          </Pressable>
          <Pressable onPress={() => setEditing(false)}>
            <Text style={styles.link}>Скасувати</Text>
          </Pressable>
        </>
      ) : (
        <>
          <Text style={styles.title}>{post.title}</Text>
          <Text style={styles.body}>{post.text}</Text>
        </>
      )}

      <Pressable
        onPress={like}
        style={styles.likeRow}
        accessibilityRole="button"
        accessibilityLabel={`Вподобайка ${post.likes_count}`}
      >
        <Ionicons
          name={post.liked_by_me ? "heart" : "heart-outline"}
          size={22}
          color="#E11D48"
        />
        <Text style={[styles.like, post.liked_by_me && styles.likeOn]}>
          {post.likes_count}
        </Text>
      </Pressable>

      {mine && !editing && (
        <View style={styles.row}>
          <Pressable
            onPress={() => setEditing(true)}
            accessibilityRole="button"
            accessibilityLabel="Редагувати"
            hitSlop={8}
          >
            <Ionicons name="create-outline" size={22} color={colors.ink} />
          </Pressable>
          <Pressable
            onPress={remove}
            accessibilityRole="button"
            accessibilityLabel="Видалити"
            hitSlop={8}
          >
            <Ionicons name="trash-outline" size={22} color="#E11D48" />
          </Pressable>
        </View>
      )}

      <Text style={styles.sec}>Коментарі</Text>
      {(post.comments || []).map((c) => (
        <View key={c.id} style={styles.comment}>
          <UserNameLink user={c.author} style={styles.meta} />
          <Text style={styles.body}>{c.text}</Text>
        </View>
      ))}
      <View style={styles.commentSendRow}>
        <CyrillicTextInput
          style={[styles.input, { flex: 1, marginTop: 0 }]}
          placeholder="Новий коментар"
          placeholderTextColor={colors.muted}
          value={comment}
          onChangeText={setComment}
        />
        <Pressable
          style={styles.sendIconBtn}
          onPress={sendComment}
          accessibilityRole="button"
          accessibilityLabel="Відправити"
        >
          <Ionicons name="send" size={22} color={colors.white} />
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  meta: { color: colors.muted, fontSize: 13 },
  book: { color: colors.stamp, fontWeight: "700", marginTop: 4 },
  title: { fontSize: 22, fontWeight: "800", color: colors.ink, marginTop: 8 },
  body: { color: colors.ink, marginTop: 8, lineHeight: 22 },
  like: { marginTop: 0, color: colors.muted, fontWeight: "700", fontSize: 16 },
  likeOn: { color: "#E11D48", fontWeight: "800" },
  likeRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 14 },
  row: { flexDirection: "row", gap: 20, marginTop: 12, alignItems: "center" },
  link: { color: colors.ink, fontWeight: "700" },
  sec: { marginTop: 24, fontWeight: "800", color: colors.ink, marginBottom: 8 },
  comment: { borderBottomWidth: 1, borderColor: colors.line, paddingVertical: 8 },
  input: { borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, paddingVertical: 10, marginTop: 12 },
  commentSendRow: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 12 },
  sendIconBtn: {
    backgroundColor: colors.ink,
    width: 44,
    height: 44,
    borderRadius: btnRadius,
    alignItems: "center",
    justifyContent: "center",
  },
  btn: { backgroundColor: colors.ink, padding: 12, marginTop: 12, borderRadius: btnRadius },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700" },
});
