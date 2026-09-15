import { useCallback, useState } from "react";
import {
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, BrowseApi, ExchangeApi } from "../../src/api";
import { colors } from "../../src/theme";
import type { Shelf } from "../../src/types";

export default function Browse() {
  const router = useRouter();
  const [others, setOthers] = useState<Shelf[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const data = await BrowseApi.list();
    setOthers(data.others);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Каталог", e instanceof ApiError ? e.message : String(e)));
    }, [])
  );

  const borrow = async (s: Shelf) => {
    try {
      await ExchangeApi.create(s.id);
      Alert.alert("Запит", "Запит на позику надіслано.");
    } catch (e) {
      Alert.alert("Запит", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <FlatList
      style={{ flex: 1, backgroundColor: colors.paper }}
      data={others}
      keyExtractor={(s) => String(s.id)}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={async () => {
            setRefreshing(true);
            await load();
            setRefreshing(false);
          }}
        />
      }
      contentContainerStyle={{ padding: 16 }}
      renderItem={({ item }) => (
        <View style={styles.card}>
          <Pressable onPress={() => router.push(`/user/${item.user.id}`)}>
            <Text style={styles.owner}>{item.user.username}</Text>
          </Pressable>
          <Pressable onPress={() => router.push(`/book/${item.book.id}`)}>
            <Text style={styles.title}>{item.book.title}</Text>
            <Text style={styles.meta}>
              {item.book.authors} · {item.book.reader_age_summary}
            </Text>
          </Pressable>
          <Pressable style={styles.btn} onPress={() => borrow(item)}>
            <Text style={styles.btnText}>Позичити</Text>
          </Pressable>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white, padding: 12, marginBottom: 10 },
  owner: { color: colors.stamp, fontWeight: "700", marginBottom: 4 },
  title: { color: colors.ink, fontWeight: "700", fontSize: 16 },
  meta: { color: colors.muted, marginTop: 4 },
  btn: { marginTop: 10, alignSelf: "flex-start", backgroundColor: colors.ink, paddingHorizontal: 12, paddingVertical: 6 },
  btnText: { color: colors.white, fontWeight: "700" },
});
