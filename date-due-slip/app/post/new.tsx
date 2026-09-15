import { useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { ApiError, FeedApi } from "../../src/api";
import { colors } from "../../src/theme";

export default function NewPost() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");

  const submit = async (confirm = false) => {
    try {
      await FeedApi.create({ title, text, confirm_new_post: confirm });
      router.back();
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
    <View style={styles.wrap}>
      <TextInput placeholder="Заголовок" placeholderTextColor={colors.muted} style={styles.input} value={title} onChangeText={setTitle} />
      <TextInput placeholder="Текст" placeholderTextColor={colors.muted} style={[styles.input, { height: 140 }]} multiline value={text} onChangeText={setText} />
      <Pressable style={styles.btn} onPress={() => submit(false)}>
        <Text style={styles.btnText}>Опублікувати</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.paper, padding: 20 },
  input: { borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, paddingVertical: 10, marginBottom: 16 },
  btn: { backgroundColor: colors.ink, padding: 14 },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700" },
});
