import { useEffect, useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, FeedApi, ShelfApi } from "../../src/api";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { colors, fs, s } from "../../src/theme";
import type { Shelf } from "../../src/types";

type Mode = "event" | "feedback";

export default function NewPost() {
  const router = useRouter();
  const params = useLocalSearchParams<{ book_id?: string; mode?: string }>();
  const mode: Mode =
    params.mode === "feedback" || Boolean(params.book_id) ? "feedback" : "event";

  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [shelves, setShelves] = useState<Shelf[]>([]);
  const [bookId, setBookId] = useState<number | null>(
    params.book_id ? Number(params.book_id) : null
  );

  useEffect(() => {
    if (mode !== "feedback") return;
    ShelfApi.mine()
      .then((d) => setShelves(d.shelves))
      .catch(() => {});
  }, [mode]);

  useEffect(() => {
    if (params.book_id) setBookId(Number(params.book_id));
  }, [params.book_id]);

  const submit = async (confirm = false) => {
    if (mode === "feedback" && !bookId) {
      Alert.alert("Відгук", "Оберіть книгу зі своєї полиці.");
      return;
    }
    try {
      await FeedApi.create({
        title,
        text,
        book_id: mode === "feedback" ? bookId || undefined : undefined,
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
      <Text style={styles.heading}>
        {mode === "feedback" ? "Відгук про прочитану книгу" : "Подія"}
      </Text>
      <Text style={styles.hint}>
        {mode === "feedback"
          ? "Оберіть книгу з полиці та поділіться враженнями."
          : "Анонс або новина без прив’язки до книги."}
      </Text>

      <CyrillicTextInput
        placeholder="Заголовок"
        placeholderTextColor={colors.muted}
        style={styles.input}
        value={title}
        onChangeText={setTitle}
      />
      <CyrillicTextInput
        placeholder={mode === "event" ? "Опишіть подію…" : "Ваші враження…"}
        placeholderTextColor={colors.muted}
        style={[styles.input, { height: s(140) }]}
        multiline
        value={text}
        onChangeText={setText}
      />

      {mode === "feedback" && (
        <>
          <Text style={styles.sec}>Книга з полиці</Text>
          {shelves.length === 0 ? (
            <Text style={styles.empty}>Немає книг на полиці. Додайте книгу в «Моя полиця».</Text>
          ) : (
            shelves.map((s) => (
              <Pressable
                key={s.id}
                style={[styles.opt, bookId === s.book.id && styles.optOn]}
                onPress={() => setBookId(s.book.id)}
              >
                <Text style={styles.optText}>{s.book.title}</Text>
              </Pressable>
            ))
          )}
        </>
      )}

      <Pressable
        style={[styles.btn, mode === "feedback" && !bookId && styles.btnDisabled]}
        onPress={() => submit(false)}
        disabled={mode === "feedback" && !bookId}
      >
        <Text style={styles.btnText}>Опублікувати</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  heading: { fontSize: fs(20), fontWeight: "800", color: colors.ink, marginBottom: 6 },
  hint: { color: colors.muted, marginBottom: s(16), lineHeight: fs(20), fontSize: fs(14) },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: s(12),
    marginBottom: s(16),
    fontSize: fs(16),
    minHeight: s(48),
  },
  sec: { fontWeight: "700", color: colors.ink, marginBottom: 8, fontSize: fs(16) },
  empty: { color: colors.muted, marginBottom: 12, fontSize: fs(14) },
  opt: {
    borderWidth: 1,
    borderColor: colors.line,
    padding: s(12),
    marginBottom: 6,
    backgroundColor: colors.white,
  },
  optOn: { borderColor: colors.stamp, backgroundColor: colors.paperDark },
  optText: { color: colors.ink, fontSize: fs(16) },
  btn: {
    backgroundColor: colors.ink,
    padding: s(14),
    marginTop: s(16),
    minHeight: s(54),
  },
  btnDisabled: { opacity: 0.45 },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700", fontSize: fs(16) },
});
