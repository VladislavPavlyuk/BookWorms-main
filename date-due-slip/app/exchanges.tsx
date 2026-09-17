import { useCallback, useState, type ReactNode } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, ExchangeApi, MsgApi } from "../src/api";
import { useAuth } from "../src/auth";
import { exchangeChatPartnerId } from "../src/chat";
import { colors } from "../src/theme";
import type { Exchange, User } from "../src/types";

export default function Exchanges() {
  const router = useRouter();
  const { user } = useAuth();
  const [inn, setIn] = useState<Exchange[]>([]);
  const [out, setOut] = useState<Exchange[]>([]);
  const [hist, setHist] = useState<Exchange[]>([]);
  const [partners, setPartners] = useState<User[]>([]);

  const load = async () => {
    const [e, p] = await Promise.all([ExchangeApi.list(), MsgApi.partners()]);
    setIn(e.pending_in);
    setOut(e.pending_out);
    setHist(e.history);
    setPartners(p);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((err) =>
        Alert.alert("Обміни", err instanceof ApiError ? err.message : String(err))
      );
    }, [])
  );

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      await load();
    } catch (e) {
      Alert.alert("Обміни", e instanceof ApiError ? e.message : String(e));
    }
  };

  const openChat = (e: Exchange) => {
    const pid = exchangeChatPartnerId(e, user?.id);
    if (!pid) {
      Alert.alert("Чат", "Немає спільного запиту з цим користувачем.");
      return;
    }
    router.push(`/chat/${pid}`);
  };

  const ChatBtn = ({ e }: { e: Exchange }) => (
    <Pressable onPress={() => openChat(e)}>
      <Text style={styles.chat}>Чат</Text>
    </Pressable>
  );

  const Card = ({ e, actions }: { e: Exchange; actions?: ReactNode }) => (
    <View style={styles.card}>
      <Text style={styles.kind}>
        {e.kind === "borrow" ? "ПОЗИКА" : "ОБМІН"} · {e.status}
      </Text>
      <Text style={styles.title}>{e.target_shelf.book.title}</Text>
      <Text style={styles.meta}>
        {e.requester.username} → {e.shelf_owner.username}
        {e.offer_shelf ? ` · замість «${e.offer_shelf.book.title}»` : ""}
      </Text>
      <View style={styles.row}>
        <ChatBtn e={e} />
        {actions}
      </View>
    </View>
  );

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.paper }}
      contentContainerStyle={{ padding: 16 }}
    >
      <Text style={styles.h}>Вхідні</Text>
      {inn.length === 0 ? (
        <Text style={styles.empty}>немає</Text>
      ) : (
        inn.map((e) => (
          <Card
            key={e.id}
            e={e}
            actions={
              <>
                <Pressable onPress={() => run(() => ExchangeApi.accept(e.id))}>
                  <Text style={styles.ok}>Прийняти</Text>
                </Pressable>
                <Pressable onPress={() => run(() => ExchangeApi.reject(e.id))}>
                  <Text style={styles.no}>Відхилити</Text>
                </Pressable>
              </>
            }
          />
        ))
      )}

      <Text style={styles.h}>Вихідні</Text>
      {out.length === 0 ? (
        <Text style={styles.empty}>немає</Text>
      ) : (
        out.map((e) => (
          <Card
            key={e.id}
            e={e}
            actions={
              <Pressable onPress={() => run(() => ExchangeApi.cancel(e.id))}>
                <Text style={styles.no}>Скасувати</Text>
              </Pressable>
            }
          />
        ))
      )}

      <Text style={styles.h}>Чати</Text>
      {partners.length === 0 ? (
        <Text style={styles.empty}>
          Немає діалогів. Чат доступний після спільного запиту на позику або обмін.
        </Text>
      ) : (
        partners.map((p) => (
          <Pressable
            key={p.id}
            style={styles.card}
            onPress={() => router.push(`/chat/${p.id}`)}
          >
            <Text style={styles.title}>{p.username}</Text>
            <Text style={styles.meta}>{p.biography || "відкрити переписку"}</Text>
          </Pressable>
        ))
      )}

      <Text style={styles.h}>Історія</Text>
      {hist.length === 0 ? (
        <Text style={styles.empty}>немає</Text>
      ) : (
        hist.map((e) => <Card key={e.id} e={e} />)
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  h: {
    fontWeight: "800",
    color: colors.ink,
    marginTop: 12,
    marginBottom: 8,
    letterSpacing: 1,
  },
  empty: { color: colors.muted, marginBottom: 8, lineHeight: 18 },
  card: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 12,
    marginBottom: 8,
  },
  kind: { color: colors.stamp, fontSize: 11, fontWeight: "800" },
  title: { color: colors.ink, fontWeight: "700", marginTop: 4 },
  meta: { color: colors.muted, marginTop: 4, fontSize: 13 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 16, marginTop: 10, alignItems: "center" },
  chat: { color: colors.ink, fontWeight: "800" },
  ok: { color: colors.stampOk, fontWeight: "800" },
  no: { color: colors.stamp, fontWeight: "800" },
});
