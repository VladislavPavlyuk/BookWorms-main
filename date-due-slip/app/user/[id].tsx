import { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { ApiError, BrowseApi, ExchangeApi } from "../../src/api";
import { colors } from "../../src/theme";
import type { Shelf, User } from "../../src/types";

export default function UserShelf() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [owner, setOwner] = useState<User | null>(null);
  const [shelves, setShelves] = useState<Shelf[]>([]);

  useEffect(() => {
    BrowseApi.user(Number(id))
      .then((d) => {
        setOwner(d.user);
        setShelves(d.shelves);
      })
      .catch((e) => Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e)));
  }, [id]);

  const borrow = async (s: Shelf) => {
    try {
      await ExchangeApi.create(s.id);
      Alert.alert("Запит", "Надіслано.");
    } catch (e) {
      Alert.alert("Запит", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.paper }} contentContainerStyle={{ padding: 16 }}>
      <Text style={styles.h}>{owner?.username}</Text>
      <Text style={styles.bio}>{owner?.biography}</Text>
      {shelves.map((s) => (
        <View key={s.id} style={styles.card}>
          <Text style={styles.title}>{s.book.title}</Text>
          <Text style={styles.meta}>
            {s.borrowed_from ? `позичено у ${s.borrowed_from.username}` : "власна"}
            {s.due_date ? ` · до ${s.due_date}` : ""}
          </Text>
          {!s.borrowed_from && (
            <Pressable onPress={() => borrow(s)}>
              <Text style={styles.act}>Позичити</Text>
            </Pressable>
          )}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  h: { fontSize: 22, fontWeight: "800", color: colors.ink },
  bio: { color: colors.muted, marginBottom: 16 },
  card: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white, padding: 12, marginBottom: 8 },
  title: { fontWeight: "700", color: colors.ink },
  meta: { color: colors.muted, marginTop: 4 },
  act: { color: colors.stamp, fontWeight: "800", marginTop: 8 },
});
