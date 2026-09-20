import { useEffect, useState } from "react";
import { Alert, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, CopyApi } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { colors } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
import type { BookCopyDetail, CopyEvent, Shelf } from "../../src/types";

export default function CopyHistoryScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [copy, setCopy] = useState<BookCopyDetail | null>(null);
  const [holders, setHolders] = useState<Shelf[]>([]);
  const [events, setEvents] = useState<CopyEvent[]>([]);

  useEffect(() => {
    CopyApi.history(Number(id))
      .then((d) => {
        setCopy(d.copy);
        setHolders(d.holders);
        setEvents(d.events);
      })
      .catch((e) =>
        Alert.alert("Історія", e instanceof ApiError ? e.message : String(e))
      );
  }, [id]);

  if (!copy) return null;
  const book = copy.book;

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.screen }} contentContainerStyle={{ paddingBottom: 32 }}>
      <BookCover uri={book.cover_url} size="full" bleed={0} />
      <View style={styles.body}>
        <Text style={styles.copyTag}>Примірник #{copy.id}</Text>
        <Text style={styles.title} onPress={() => router.push(`/book/${book.id}`)}>
          {book.title}
        </Text>
        <Text style={styles.meta}>{book.authors || "—"}</Text>
        <Text style={styles.meta}>ISBN {book.isbn}</Text>
        <View style={styles.row}>
          <Text style={styles.meta}>Власник: </Text>
          <UserNameLink user={copy.owner} style={styles.link} />
        </View>

        <Text style={styles.h}>Хронологія подій</Text>
        {events.length === 0 ? (
          <Text style={styles.meta}>Подій ще немає.</Text>
        ) : (
          events.map((ev) => (
            <View key={ev.id} style={styles.card}>
              <Text style={styles.evCode}>{ev.code_display}</Text>
              <Text style={styles.evTime}>
                {new Date(ev.created_at).toLocaleString("uk-UA")}
              </Text>
              {ev.legal_owner ? (
                <View style={styles.row}>
                  <Text style={styles.meta}>Власник: </Text>
                  <UserNameLink user={ev.legal_owner} style={styles.meta} />
                </View>
              ) : null}
              {ev.holder ? (
                <View style={styles.row}>
                  <Text style={styles.meta}>На полиці: </Text>
                  <UserNameLink user={ev.holder} style={styles.meta} />
                </View>
              ) : null}
              {ev.previous_holder ? (
                <View style={styles.row}>
                  <Text style={styles.meta}>Було: </Text>
                  <UserNameLink user={ev.previous_holder} style={styles.meta} />
                </View>
              ) : null}
              {ev.counterparty ? (
                <View style={styles.row}>
                  <Text style={styles.meta}>Учасник: </Text>
                  <UserNameLink user={ev.counterparty} style={styles.meta} />
                </View>
              ) : null}
              {ev.actor ? (
                <View style={styles.row}>
                  <Text style={styles.meta}>Ініціатор: </Text>
                  <UserNameLink user={ev.actor} style={styles.meta} />
                </View>
              ) : null}
            </View>
          ))
        )}

        <Text style={styles.h}>Поточний стан</Text>
        {holders.length === 0 ? (
          <Text style={styles.meta}>Ні на чиїй полиці.</Text>
        ) : (
          holders.map((s) => (
            <View key={s.id} style={styles.card}>
              <View style={styles.row}>
                <UserNameLink user={s.user} style={styles.link} />
                <Text style={styles.meta}>
                  {s.borrowed_from ? " · позика" : " · власник"}
                </Text>
              </View>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  body: { paddingHorizontal: 16, paddingTop: 12 },
  copyTag: { color: colors.stamp, fontWeight: "800", letterSpacing: 0.5, marginBottom: 4 },
  title: { fontSize: 22, fontWeight: "800", color: colors.ink },
  meta: { color: colors.muted, marginTop: 2 },
  link: { color: colors.stamp, fontWeight: "700" },
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", marginTop: 2 },
  h: { marginTop: 24, fontWeight: "800", color: colors.ink, marginBottom: 8 },
  card: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 12,
    marginBottom: 8,
  },
  evCode: { color: colors.ink, fontWeight: "800" },
  evTime: { color: colors.muted, fontSize: 12, marginTop: 2, marginBottom: 6 },
});
