import { useCallback, useState } from "react";
import {
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, NotifApi, type AppNotification } from "../src/api";
import { formatMsgTime } from "../src/chat";
import { colors } from "../src/theme";

export default function NotificationsScreen() {
  const router = useRouter();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const data = await NotifApi.list();
    setItems(data.results);
    setUnread(data.unread_count);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) =>
        Alert.alert("Сповіщення", e instanceof ApiError ? e.message : String(e))
      );
    }, [])
  );

  const markAll = async () => {
    try {
      const r = await NotifApi.markRead();
      setUnread(r.unread_count);
      await load();
    } catch (e) {
      Alert.alert("Сповіщення", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.paper }}
      contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
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
    >
      <Text style={styles.h}>Сповіщення</Text>
      <Text style={styles.hint}>
        Запити на позику/обмін. Звідси — одразу в чат зі співрозмовником.
        {unread ? ` Непрочитаних: ${unread}.` : ""}
      </Text>

      <View style={styles.actions}>
        <Pressable onPress={() => router.push("/exchanges")}>
          <Text style={styles.link}>Обміни</Text>
        </Pressable>
        {unread > 0 && (
          <Pressable onPress={markAll}>
            <Text style={styles.link}>Прочитати все</Text>
          </Pressable>
        )}
      </View>

      {items.length === 0 ? (
        <Text style={styles.empty}>Поки немає сповіщень.</Text>
      ) : (
        items.map((n) => (
          <View
            key={n.id}
            style={[styles.card, n.is_unread && styles.unread]}
          >
            <Text style={styles.meta}>
              від {n.chat_partner_username}
              {" · "}
              {formatMsgTime(n.created_at)}
              {n.is_unread ? " · нове" : ""}
              {n.kind === "exchange" ? " · запит" : ""}
            </Text>
            <Text style={styles.body}>{n.body}</Text>
            <View style={styles.row}>
              <Pressable
                onPress={() => router.push(`/chat/${n.chat_partner_id}`)}
              >
                <Text style={styles.chat}>Відкрити чат</Text>
              </Pressable>
              {n.exchange_request_id != null && (
                <Pressable onPress={() => router.push("/exchanges")}>
                  <Text style={styles.ex}>До обмінів</Text>
                </Pressable>
              )}
            </View>
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  h: { fontSize: 22, fontWeight: "800", color: colors.ink },
  hint: { color: colors.muted, marginTop: 6, marginBottom: 12, lineHeight: 18 },
  actions: { flexDirection: "row", gap: 16, marginBottom: 12 },
  link: { color: colors.stamp, fontWeight: "800" },
  empty: { color: colors.muted, marginTop: 24 },
  card: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 12,
    marginBottom: 10,
  },
  unread: { borderColor: colors.stamp, backgroundColor: "#FBE9E5" },
  meta: { color: colors.muted, fontSize: 12, marginBottom: 6 },
  body: { color: colors.ink, lineHeight: 20 },
  row: { flexDirection: "row", gap: 16, marginTop: 10 },
  chat: { color: colors.ink, fontWeight: "800" },
  ex: { color: colors.stampOk, fontWeight: "800" },
});
