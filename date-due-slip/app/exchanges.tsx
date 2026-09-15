import { useCallback, useState, type ReactNode } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, ExchangeApi, MsgApi } from "../src/api";
import { colors } from "../src/theme";
import type { Exchange, User } from "../src/types";

export default function Exchanges() {
  const router = useRouter();
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
      load().catch((err) => Alert.alert("Обміни", err instanceof ApiError ? err.message : String(err)));
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

  const Card = ({ e, actions }: { e: Exchange; actions?: ReactNode }) => (
    <View style={styles.card}>
      <Text style={styles.kind}>{e.kind === "borrow" ? "ПОЗИКА" : "ОБМІН"} · {e.status}</Text>
      <Text style={styles.title}>{e.target_shelf.book.title}</Text>
      <Text style={styles.meta}>
        {e.requester.username} → {e.shelf_owner.username}
        {e.offer_shelf ? ` · замість «${e.offer_shelf.book.title}»` : ""}
      </Text>
      {actions}
    </View>
  );

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.paper }} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.h}>Вхідні</Text>
      {inn.length === 0 ? <Text style={styles.empty}>немає</Text> : inn.map((e) => (
        <Card
          key={e.id}
          e={e}
          actions={
            <View style={styles.row}>
              <Pressable onPress={() => run(() => ExchangeApi.accept(e.id))}><Text style={styles.ok}>Прийняти</Text></Pressable>
              <Pressable onPress={() => run(() => ExchangeApi.reject(e.id))}><Text style={styles.no}>Відхилити</Text></Pressable>
            </View>
          }
        />
      ))}
      <Text style={styles.h}>Вихідні</Text>
      {out.length === 0 ? <Text style={styles.empty}>немає</Text> : out.map((e) => (
        <Card
          key={e.id}
          e={e}
          actions={<Pressable onPress={() => run(() => ExchangeApi.cancel(e.id))}><Text style={styles.no}>Скасувати</Text></Pressable>}
        />
      ))}
      <Text style={styles.h}>Чати</Text>
      {partners.map((p) => (
        <Pressable key={p.id} style={styles.card} onPress={() => router.push(`/chat/${p.id}`)}>
          <Text style={styles.title}>{p.username}</Text>
        </Pressable>
      ))}
      <Text style={styles.h}>Історія</Text>
      {hist.map((e) => <Card key={e.id} e={e} />)}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  h: { fontWeight: "800", color: colors.ink, marginTop: 12, marginBottom: 8, letterSpacing: 1 },
  empty: { color: colors.muted, marginBottom: 8 },
  card: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white, padding: 12, marginBottom: 8 },
  kind: { color: colors.stamp, fontSize: 11, fontWeight: "800" },
  title: { color: colors.ink, fontWeight: "700", marginTop: 4 },
  meta: { color: colors.muted, marginTop: 4, fontSize: 13 },
  row: { flexDirection: "row", gap: 16, marginTop: 8 },
  ok: { color: colors.stampOk, fontWeight: "800" },
  no: { color: colors.stamp, fontWeight: "800", marginTop: 8 },
});
