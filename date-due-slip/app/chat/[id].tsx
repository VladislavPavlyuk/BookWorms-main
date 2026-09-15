import { useCallback, useState } from "react";
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useFocusEffect } from "expo-router";
import { ApiError, MsgApi } from "../../src/api";
import { useAuth } from "../../src/auth";
import { colors } from "../../src/theme";
import type { Message } from "../../src/types";

export default function Chat() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [partner, setPartner] = useState("");
  const [body, setBody] = useState("");

  const load = async () => {
    const data = await MsgApi.thread(Number(id));
    setMessages(data.messages);
    setPartner(data.partner.username);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Чат", e instanceof ApiError ? e.message : String(e)));
    }, [id])
  );

  const send = async () => {
    try {
      await MsgApi.send(Number(id), body);
      setBody("");
      await load();
    } catch (e) {
      Alert.alert("Чат", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.paper }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Text style={styles.head}>{partner}</Text>
      <FlatList
        data={messages}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={{ padding: 12 }}
        renderItem={({ item }) => {
          const mine = item.sender.id === user?.id;
          return (
            <View style={[styles.bubble, mine ? styles.mine : styles.theirs]}>
              <Text style={styles.msg}>{item.body}</Text>
            </View>
          );
        }}
      />
      <View style={styles.bar}>
        <TextInput style={styles.input} value={body} onChangeText={setBody} placeholder="повідомлення" placeholderTextColor={colors.muted} />
        <Pressable onPress={send}><Text style={styles.send}>Надіслати</Text></Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  head: { padding: 12, fontWeight: "800", color: colors.ink, borderBottomWidth: 1, borderColor: colors.line },
  bubble: { maxWidth: "80%", padding: 10, marginBottom: 8 },
  mine: { alignSelf: "flex-end", backgroundColor: colors.paperDark },
  theirs: { alignSelf: "flex-start", backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line },
  msg: { color: colors.ink },
  bar: { flexDirection: "row", alignItems: "center", padding: 10, borderTopWidth: 1, borderColor: colors.line, gap: 8 },
  input: { flex: 1, color: colors.ink, borderBottomWidth: 1, borderColor: colors.line, paddingVertical: 6 },
  send: { color: colors.stamp, fontWeight: "800" },
});
