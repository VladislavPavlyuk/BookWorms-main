import { useEffect, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, FeedApi, ShelfApi } from "../../src/api";
import { colors } from "../../src/theme";
import type { Shelf } from "../../src/types";

export default function NewPost() {
  const router = useRouter();
  const params = useLocalSearchParams<{ book_id?: string }>();
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [shelves, setShelves] = useState<Shelf[]>([]);
  const [bookId, setBookId] = useState<number | null>(
    params.book_id ? Number(params.book_id) : null
  );

  useEffect(() => {
    ShelfApi.mine()
      .then((d) => setShelves(d.shelves))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (params.book_id) setBookId(Number(params.book_id));
  }, [params.book_id]);

  const submit = async (confirm = false) => {
    try {
      await FeedApi.create({
        title,
        text,
        book_id: bookId || undefined,
        confirm_new_post: confirm,
      });
      router.replace("/(tabs)");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        Alert.alert("Схожі пости", "Інші вже писали про цю книгу. Опублікувати все одно?", [
          { text: "Ні" },
          { text: "Так", onPress: () => submit(true) },
        ]);
        return;
      }
      Alert.alert("Пост", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.screen }} contentContainerStyle={{ padding: 20 }}>
      <TextInput
        placeholder="Заголовок"
        placeholderTextColor={colors.muted}
        style={styles.input}
        value={title}
        onChangeText={setTitle}
      />
      <TextInput
        placeholder="Текст"
        placeholderTextColor={colors.muted}
        style={[styles.input, { height: 140 }]}
        multiline
        value={text}
        onChangeText={setText}
      />

      <Text style={styles.sec}>Книга з полиці (необов'язково)</Text>
      <Pressable
        style={[styles.opt, bookId === null && styles.optOn]}
        onPress={() => setBookId(null)}
      >
        <Text style={styles.optText}>Без книги</Text>
      </Pressable>
      {shelves.map((s) => (
        <Pressable
          key={s.id}
          style={[styles.opt, bookId === s.book.id && styles.optOn]}
          onPress={() => setBookId(s.book.id)}
        >
          <Text style={styles.optText}>{s.book.title}</Text>
        </Pressable>
      ))}

      <Pressable style={styles.btn} onPress={() => submit(false)}>
        <Text style={styles.btnText}>Опублікувати</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: 10,
    marginBottom: 16,
  },
  sec: { fontWeight: "700", color: colors.ink, marginBottom: 8 },
  opt: {
    borderWidth: 1,
    borderColor: colors.line,
    padding: 10,
    marginBottom: 6,
    backgroundColor: colors.white,
  },
  optOn: { borderColor: colors.stamp, backgroundColor: colors.paperDark },
  optText: { color: colors.ink },
  btn: { backgroundColor: colors.ink, padding: 14, marginTop: 16 },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700" },
});
