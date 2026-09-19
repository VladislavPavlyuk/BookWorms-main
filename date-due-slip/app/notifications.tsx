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
import { ApiError, NotifApi, ShelfApi, type AppNotification } from "../src/api";
import { formatMsgTime } from "../src/chat";
import { colors } from "../src/theme";
import { useUnread } from "../src/unread";

export default function NotificationsScreen() {
  const router = useRouter();
  const { unread, setUnread, refresh: refreshBadge } = useUnread();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const data = await NotifApi.list();
    setItems(data.results);
    setUnread(data.unread_count);
  };

  useFocusEffect(
    useCallback(() => {
      load()
        .then(() => refreshBadge())
        .catch((e) =>
          Alert.alert("Сповіщення", e instanceof ApiError ? e.message : String(e))
        );
    }, [refreshBadge, setUnread])
  );

  const openChat = async (n: AppNotification) => {
    if (n.is_unread) {
      try {
        const r = await NotifApi.markRead([n.id]);
        setUnread(r.unread_count);
        setItems((prev) =>
          prev.map((x) =>
            x.id === n.id
              ? { ...x, is_unread: false, read_at: new Date().toISOString() }
              : x
          )
        );
      } catch {
        /* чат все одно відкриємо */
      }
    }
    router.push(`/chat/${n.chat_partner_id}`);
  };

  const openExchanges = async (n?: AppNotification) => {
    if (n?.is_unread) {
      try {
        const r = await NotifApi.markRead([n.id]);
        setUnread(r.unread_count);
        setItems((prev) =>
          prev.map((x) =>
            x.id === n.id
              ? { ...x, is_unread: false, read_at: new Date().toISOString() }
              : x
          )
        );
      } catch {
        /* все одно йдемо на обміни */
      }
    }
    if (n?.exchange_request_id != null) {
      router.push(`/exchanges?id=${n.exchange_request_id}`);
    } else {
      router.push("/exchanges");
    }
  };

  const confirmReturn = async (n: AppNotification) => {
    const shelfId = n.confirm_return_shelf_id;
    if (!shelfId) return;
    try {
      await ShelfApi.confirmReturn(shelfId);
      try {
        const r = await NotifApi.markRead([n.id]);
        setUnread(r.unread_count);
      } catch {
        /* ok */
      }
      Alert.alert("Повернення", "Підтверджено.");
      await load();
      await refreshBadge();
    } catch (e) {
      Alert.alert("Повернення", e instanceof ApiError ? e.message : String(e));
    }
  };

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
      style={{ flex: 1, backgroundColor: colors.screen }}
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
        Запит на книгу → «Обміни»: умови (позика/обмін), чат за потреби, прийняти або відхилити.
        {unread ? ` Непрочитаних: ${unread}.` : ""}
      </Text>

      <View style={styles.actions}>
        <Pressable onPress={() => openExchanges()}>
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
              {n.kind === "return" ? " · повернення" : ""}
            </Text>
            <Text style={styles.body}>{n.body}</Text>
            <View style={styles.row}>
              {n.kind === "return" && n.confirm_return_shelf_id != null ? (
                <Pressable style={styles.confirmBtn} onPress={() => confirmReturn(n)}>
                  <Text style={styles.confirmBtnText}>Підтвердити</Text>
                </Pressable>
              ) : null}
              {n.exchange_request_id != null ? (
                <Pressable onPress={() => openExchanges(n)}>
                  <Text style={styles.chat}>До обмінів</Text>
                </Pressable>
              ) : null}
              <Pressable onPress={() => openChat(n)}>
                <Text style={styles.ex}>Чат</Text>
              </Pressable>
              {n.is_unread && (
                <Pressable
                  onPress={async () => {
                    try {
                      const r = await NotifApi.markRead([n.id]);
                      setUnread(r.unread_count);
                      setItems((prev) =>
                        prev.map((x) =>
                          x.id === n.id
                            ? {
                                ...x,
                                is_unread: false,
                                read_at: new Date().toISOString(),
                              }
                            : x
                        )
                      );
                    } catch (e) {
                      Alert.alert(
                        "Сповіщення",
                        e instanceof ApiError ? e.message : String(e)
                      );
                    }
                  }}
                >
                  <Text style={styles.ex}>Прочитано</Text>
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
  row: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginTop: 10, alignItems: "center" },
  confirmBtn: {
    backgroundColor: colors.stampOk,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  confirmBtnText: { color: "#fff", fontWeight: "800" },
  chat: { color: colors.ink, fontWeight: "800" },
  ex: { color: colors.stampOk, fontWeight: "800" },
});
