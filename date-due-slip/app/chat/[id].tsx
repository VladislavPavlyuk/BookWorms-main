import { useCallback, useRef, useState } from "react";
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, MsgApi } from "../../src/api";
import { useAuth } from "../../src/auth";
import { formatMsgTime, otherPartners } from "../../src/chat";
import { colors } from "../../src/theme";
import type { Message, User } from "../../src/types";

export default function Chat() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const partnerId = Number(id);
  const { user } = useAuth();
  const router = useRouter();
  const listRef = useRef<FlatList<Message>>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [partner, setPartner] = useState<User | null>(null);
  const [partners, setPartners] = useState<User[]>([]);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const [thread, plist] = await Promise.all([
      MsgApi.thread(partnerId),
      MsgApi.partners().catch(() => [] as User[]),
    ]);
    setMessages(thread.messages);
    setPartner(thread.partner);
    setPartners(plist);
    requestAnimationFrame(() => {
      if (thread.messages.length) {
        listRef.current?.scrollToEnd({ animated: false });
      }
    });
  };

  useFocusEffect(
    useCallback(() => {
      if (!partnerId) return;
      load().catch((e) =>
        Alert.alert("Чат", e instanceof ApiError ? e.message : String(e), [
          { text: "До обмінів", onPress: () => router.replace("/exchanges") },
          { text: "OK" },
        ])
      );
      // легкий polling як на десктопі немає WS — раз на 8с поки екран у фокусі
      const t = setInterval(() => {
        load().catch(() => undefined);
      }, 8000);
      return () => clearInterval(t);
    }, [partnerId])
  );

  const send = async () => {
    const text = body.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      await MsgApi.send(partnerId, text);
      setBody("");
      await load();
      requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
    } catch (e) {
      Alert.alert("Чат", e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const others = partner ? otherPartners(partners, partner.id) : [];

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.screen }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 64 : 0}
    >
      <View style={styles.head}>
        <Text style={styles.headTitle}>{partner?.username || "…"}</Text>
        <Text style={styles.headHint}>
          Діалог лише зі спільним запитом на позику/обмін. Вхідні зліва, ваші — справа.
        </Text>
        <Pressable onPress={() => router.push("/exchanges")}>
          <Text style={styles.back}>← До обмінів</Text>
        </Pressable>
      </View>

      {others.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.othersBar}
          contentContainerStyle={{ paddingHorizontal: 12, gap: 8 }}
        >
          <Text style={styles.othersLabel}>Інші:</Text>
          {others.map((p) => (
            <Pressable key={p.id} onPress={() => router.replace(`/chat/${p.id}`)}>
              <Text style={styles.otherChip}>{p.username}</Text>
            </Pressable>
          ))}
        </ScrollView>
      )}

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={{ padding: 12, flexGrow: 1 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={async () => {
              setRefreshing(true);
              try {
                await load();
              } finally {
                setRefreshing(false);
              }
            }}
          />
        }
        ListEmptyComponent={
          <Text style={styles.empty}>Ще немає повідомлень у цьому чаті.</Text>
        }
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
        renderItem={({ item }) => {
          const mine = item.sender.id === user?.id;
          const inbound = item.recipient.id === user?.id;
          return (
            <View style={[styles.bubble, mine ? styles.mine : styles.theirs]}>
              <Text style={styles.meta}>
                <Text style={styles.metaStrong}>{mine ? "Ви" : item.sender.username}</Text>
                {" · "}
                {formatMsgTime(item.created_at)}
                {inbound && item.read_at ? " · прочитано" : ""}
              </Text>
              <Text style={[styles.msg, mine && styles.msgMine]}>{item.body}</Text>
              {item.exchange_request != null && (
                <Pressable onPress={() => router.push("/exchanges")}>
                  <Text style={styles.exLink}>Запити на обмін / позику</Text>
                </Pressable>
              )}
            </View>
          );
        }}
      />

      <View style={styles.bar}>
        <TextInput
          style={styles.input}
          value={body}
          onChangeText={setBody}
          placeholder="повідомлення"
          placeholderTextColor={colors.muted}
          multiline
          editable={!busy}
        />
        <Pressable onPress={send} disabled={busy || !body.trim()}>
          <Text style={[styles.send, (!body.trim() || busy) && { opacity: 0.4 }]}>
            Надіслати
          </Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  head: {
    paddingHorizontal: 12,
    paddingTop: 12,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
  },
  headTitle: { fontWeight: "800", color: colors.ink, fontSize: 18 },
  headHint: { color: colors.muted, fontSize: 12, marginTop: 4, lineHeight: 16 },
  back: { color: colors.stamp, fontWeight: "700", marginTop: 6, fontSize: 13 },
  othersBar: { maxHeight: 40, borderBottomWidth: 1, borderColor: colors.line },
  othersLabel: { color: colors.muted, alignSelf: "center", marginRight: 4, fontSize: 12 },
  otherChip: {
    color: colors.ink,
    fontWeight: "700",
    paddingVertical: 8,
    paddingHorizontal: 4,
    fontSize: 13,
  },
  empty: { color: colors.muted, textAlign: "center", marginTop: 48 },
  bubble: { maxWidth: "82%", padding: 10, marginBottom: 10 },
  mine: { alignSelf: "flex-end", backgroundColor: colors.ink },
  theirs: {
    alignSelf: "flex-start",
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
  },
  meta: { fontSize: 11, marginBottom: 4, color: colors.muted },
  metaStrong: { fontWeight: "700", color: colors.muted },
  msg: { color: colors.ink, fontSize: 15, lineHeight: 20 },
  msgMine: { color: colors.white },
  exLink: { marginTop: 8, fontSize: 12, fontWeight: "700", color: colors.stampOk },
  bar: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: 10,
    borderTopWidth: 1,
    borderColor: colors.line,
    gap: 8,
    backgroundColor: colors.paper,
  },
  input: {
    flex: 1,
    color: colors.ink,
    borderBottomWidth: 1,
    borderColor: colors.line,
    paddingVertical: 6,
    maxHeight: 100,
  },
  send: { color: colors.stamp, fontWeight: "800", paddingBottom: 6 },
});
