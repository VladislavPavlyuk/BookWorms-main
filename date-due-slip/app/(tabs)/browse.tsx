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
import { ApiError, BrowseApi } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { RequestModal } from "../../src/RequestModal";
import { colors } from "../../src/theme";
import type { BookBrowseGroup, Shelf } from "../../src/types";

/** Client-side ISBN grouping when API has no others_grouped yet. */
function groupShelvesByBook(others: Shelf[]): BookBrowseGroup[] {
  const map = new Map<number, BookBrowseGroup>();
  const order: number[] = [];
  for (const s of others) {
    let g = map.get(s.book.id);
    if (!g) {
      g = { book: s.book, owners: [], copies: [] };
      map.set(s.book.id, g);
      order.push(s.book.id);
    }
    g.copies.push(s);
    if (!g.owners.some((o) => o.id === s.user.id)) g.owners.push(s.user);
  }
  return order.map((id) => map.get(id)!);
}

export default function Browse() {
  const router = useRouter();
  const [groups, setGroups] = useState<BookBrowseGroup[]>([]);
  const [myOwned, setMyOwned] = useState<Shelf[]>([]);
  const [target, setTarget] = useState<Shelf | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const data = await BrowseApi.list();
    const grouped =
      data.others_grouped && data.others_grouped.length > 0
        ? data.others_grouped
        : groupShelvesByBook(data.others || []);
    setGroups(grouped);
    setMyOwned(data.my_owned || []);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Каталог", e instanceof ApiError ? e.message : String(e)));
    }, [])
  );

  const requestFrom = (g: BookBrowseGroup, ownerId?: number) => {
    const copies = ownerId
      ? g.copies.filter((c) => c.user.id === ownerId)
      : g.copies;
    if (copies.length === 1) {
      setTarget(copies[0]);
      return;
    }
    if (copies.length === 0) return;
    Alert.alert(
      "Власник",
      "Оберіть у кого позичити",
      [
        ...copies.map((c) => ({
          text: c.user.username,
          onPress: () => setTarget(c),
        })),
        { text: "Скасувати", style: "cancel" as const },
      ]
    );
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.screen }}>
      <FlatList
        data={groups}
        keyExtractor={(g) => String(g.book.id)}
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
        contentContainerStyle={{ paddingBottom: 24 }}
        ListEmptyComponent={<Text style={styles.empty}>Немає чужих книг</Text>}
        renderItem={({ item: g }) => (
          <View style={styles.card}>
            <Pressable onPress={() => router.push(`/book/${g.book.id}`)}>
              <BookCover uri={g.book.cover_url} size="full" bleed={0} />
              <View style={styles.cardBody}>
                <Text style={styles.title}>{g.book.title}</Text>
                <Text style={styles.meta}>
                  {g.book.authors} · {g.book.reader_age_summary}
                </Text>
                <View style={styles.ownersRow}>
                  <Text style={styles.ownersLabel}>Власники: </Text>
                  {g.owners.map((o, i) => (
                    <Pressable key={o.id} onPress={() => router.push(`/user/${o.id}`)}>
                      <Text style={styles.owner}>
                        {i > 0 ? " · " : ""}
                        {o.username}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            </Pressable>
            <Pressable style={[styles.btn, styles.cardBody]} onPress={() => requestFrom(g)}>
              <Text style={styles.btnText}>Позичити / обмін</Text>
            </Pressable>
          </View>
        )}
      />
      <RequestModal
        target={target}
        myOwned={myOwned}
        onClose={() => setTarget(null)}
        onDone={() => load()}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  empty: { color: colors.muted, textAlign: "center", marginTop: 40 },
  card: {
    borderWidth: 0,
    borderBottomWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 0,
    marginBottom: 0,
    overflow: "hidden",
  },
  cardBody: { paddingHorizontal: 16, paddingBottom: 12 },
  ownersRow: { flexDirection: "row", flexWrap: "wrap", marginTop: 8, alignItems: "center" },
  ownersLabel: { color: colors.muted, fontSize: 13 },
  owner: { color: colors.stamp, fontWeight: "700", fontSize: 13 },
  title: { color: colors.ink, fontWeight: "700", fontSize: 16 },
  meta: { color: colors.muted, marginTop: 4 },
  btn: { marginTop: 10, alignSelf: "flex-start", backgroundColor: colors.ink, paddingHorizontal: 12, paddingVertical: 6 },
  btnText: { color: colors.white, fontWeight: "700" },
});
