import { useCallback, useState } from "react";
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, QueueApi } from "../src/api";
import { colors, fs, s } from "../src/theme";

type QItem = {
  id: number;
  copy_id: number;
  book_title: string;
  owner_id: number;
  owner_username: string;
  status: string;
  position: number;
  created_at: string;
};

export default function MyQueues() {
  const router = useRouter();
  const [items, setItems] = useState<QItem[]>([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setErr("");
    try {
      const data = await QueueApi.mine();
      setItems(data.results || []);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.screen }}>
      <Text style={styles.head}>Мої черги</Text>
      {err ? <Text style={styles.err}>{err}</Text> : null}
      <FlatList
        data={items}
        keyExtractor={(it) => String(it.id)}
        refreshControl={<RefreshControl refreshing={busy} onRefresh={load} />}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        ListEmptyComponent={
          !busy ? <Text style={styles.empty}>Немає активних черг.</Text> : null
        }
        renderItem={({ item }) => (
          <Pressable
            style={styles.card}
            onPress={() => router.push(`/copy/${item.copy_id}`)}
          >
            <Text style={styles.title}>{item.book_title}</Text>
            <Text style={styles.meta}>
              власник @{item.owner_username} · місце {item.position} · {item.status}
            </Text>
            <Text style={styles.meta}>#{item.copy_id}</Text>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  head: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    fontSize: fs(20),
    fontWeight: "800",
    color: colors.ink,
  },
  err: { color: colors.danger, paddingHorizontal: 16, marginBottom: 8 },
  empty: { color: colors.muted, fontSize: fs(15), marginTop: 24 },
  card: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    paddingVertical: s(14),
  },
  title: { color: colors.ink, fontSize: fs(16), fontWeight: "700" },
  meta: { color: colors.muted, fontSize: fs(13), marginTop: 4 },
});
