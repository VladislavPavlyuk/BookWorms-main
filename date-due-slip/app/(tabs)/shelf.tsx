import { useCallback, useState } from "react";
import {
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, ShelfApi } from "../../src/api";
import { colors } from "../../src/theme";
import type { Shelf } from "../../src/types";

export default function ShelfScreen() {
  const router = useRouter();
  const [shelves, setShelves] = useState<Shelf[]>([]);
  const [pending, setPending] = useState<Shelf[]>([]);
  const [isbn, setIsbn] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const data = await ShelfApi.mine();
    setShelves(data.shelves);
    setPending(data.pending_returns);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e)));
    }, [])
  );

  const add = async () => {
    try {
      await ShelfApi.addIsbn(isbn.trim());
      setIsbn("");
      await load();
    } catch (e) {
      Alert.alert("ISBN", e instanceof ApiError ? e.message : String(e));
    }
  };

  const act = async (s: Shelf) => {
    try {
      if (s.borrowed_from) await ShelfApi.returnBook(s.id);
      else await ShelfApi.remove(s.id);
      await load();
    } catch (e) {
      Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e));
    }
  };

  const confirm = async (s: Shelf) => {
    try {
      await ShelfApi.confirmReturn(s.id);
      await load();
    } catch (e) {
      Alert.alert("Повернення", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.paper }}>
      <View style={styles.row}>
        <TextInput
          placeholder="ISBN 10/13"
          placeholderTextColor={colors.muted}
          style={styles.input}
          value={isbn}
          onChangeText={setIsbn}
          autoCapitalize="none"
        />
        <Pressable style={styles.add} onPress={add}>
          <Text style={styles.addText}>Додати</Text>
        </Pressable>
      </View>
      <FlatList
        data={shelves}
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
        ListHeaderComponent={
          pending.length ? (
            <View style={{ paddingHorizontal: 16 }}>
              <Text style={styles.sec}>Очікують вашого підтвердження</Text>
              {pending.map((s) => (
                <Pressable key={s.id} style={styles.card} onPress={() => confirm(s)}>
                  <Text style={styles.title}>{s.book.title}</Text>
                  <Text style={styles.meta}>{s.user.username} повертає → натисни щоб підтвердити</Text>
                </Pressable>
              ))}
            </View>
          ) : null
        }
        contentContainerStyle={{ padding: 16 }}
        renderItem={({ item }) => (
          <Pressable style={styles.card} onPress={() => router.push(`/book/${item.book.id}`)}>
            <Text style={styles.title}>{item.book.title}</Text>
            <Text style={styles.meta}>
              {item.book.authors}
              {item.borrowed_from ? ` · позичено у ${item.borrowed_from.username}` : ""}
              {item.due_date ? ` · до ${item.due_date}` : ""}
              {item.return_pending ? " · очікує підтвердження" : ""}
            </Text>
            <Pressable onPress={() => act(item)}>
              <Text style={styles.action}>
                {item.borrowed_from ? "Повернути власнику" : "Прибрати з полиці"}
              </Text>
            </Pressable>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", padding: 12, gap: 8 },
  input: { flex: 1, borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, paddingVertical: 8 },
  add: { backgroundColor: colors.ink, paddingHorizontal: 12, justifyContent: "center" },
  addText: { color: colors.white, fontWeight: "700" },
  sec: { color: colors.stamp, fontWeight: "700", marginBottom: 8 },
  card: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white, padding: 12, marginBottom: 10 },
  title: { color: colors.ink, fontWeight: "700", fontSize: 16 },
  meta: { color: colors.muted, marginTop: 4, fontSize: 13 },
  action: { color: colors.stamp, marginTop: 8, fontWeight: "700" },
});
