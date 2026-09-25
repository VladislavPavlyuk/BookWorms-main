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
import { HistoryLink } from "../../src/HistoryLink";
import { RequestModal } from "../../src/RequestModal";
import { colors, btnRadius } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
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
    const legal = s.borrowed_from || s.user;
    if (!g.owners.some((o) => o.id === legal.id)) g.owners.push(legal);
  }
  return order.map((id) => map.get(id)!);
}

function isHeldLoan(c: Shelf) {
  return !!(c.borrowed_from || c.is_lent_out || c.lent_to);
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

  const openRequest = (c: Shelf) => {
    const rid = c.request_shelf_id ?? c.id;
    if (c.borrowed_from) {
      setTarget({
        ...c,
        id: rid,
        user: c.borrowed_from,
        borrowed_from: null,
        is_lent_out: true,
        lent_to: c.user,
        loan_due_date: c.due_date,
        request_shelf_id: rid,
      });
      return;
    }
    setTarget(c);
  };

  const requestFrom = (g: BookBrowseGroup) => {
    const copies = g.copies || [];
    if (copies.length === 1) {
      openRequest(copies[0]);
      return;
    }
    if (copies.length === 0) return;
    Alert.alert(
      "Примірник",
      "Оберіть у кого зараз книга",
      [
        ...copies.map((c) => ({
          text: isHeldLoan(c)
            ? `${c.user.username} (позика · ${c.borrowed_from?.username || "власник"})`
            : c.user.username,
          onPress: () => openRequest(c),
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
        ListHeaderComponent={
          <Text style={styles.hint}>
            Каталог = фізична наявність. Позичена книга на полиці позичальника (власник і термін);
            запит іде власнику.
          </Text>
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
                    <View key={o.id} style={{ flexDirection: "row" }}>
                      {i > 0 ? <Text style={styles.ownersLabel}> · </Text> : null}
                      <UserNameLink user={o} style={styles.owner} />
                    </View>
                  ))}
                </View>
              </View>
            </Pressable>
            <View style={styles.cardBody}>
              {(g.copies?.length ? g.copies : []).map((c) => (
                <View key={c.id} style={styles.copyRow}>
                  <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", flex: 1 }}>
                    <UserNameLink user={c.user} style={styles.owner} />
                    {c.copy_id ? (
                      <Text style={styles.ownersLabel}>{` · #${c.copy_id}`}</Text>
                    ) : null}
                    {c.borrowed_from ? (
                      <Text style={styles.lent}>
                        {` · позика · власник ${c.borrowed_from.username}`}
                        {c.due_date ? ` · до ${c.due_date}` : ""}
                      </Text>
                    ) : (
                      <Text style={styles.free}> · вільний</Text>
                    )}
                  </View>
                  <Pressable onPress={() => openRequest(c)}>
                    <Text style={styles.miniAct}>
                      {c.borrowed_from ? "Передача" : "Позичити"}
                    </Text>
                  </Pressable>
                  <HistoryLink copyId={c.copy_id} />
                </View>
              ))}
            </View>
            <Pressable style={[styles.btn, styles.cardBody]} onPress={() => requestFrom(g)}>
              <Text style={styles.btnText}>Позичити / передача / обмін</Text>
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
  hint: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 16,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
  },
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
  copyRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    paddingVertical: 6,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  title: { color: colors.ink, fontWeight: "700", fontSize: 16 },
  meta: { color: colors.muted, marginTop: 4 },
  lent: { color: colors.stamp, fontWeight: "700", fontSize: 12 },
  free: { color: colors.muted, fontSize: 12 },
  miniAct: { color: colors.stamp, fontWeight: "800", fontSize: 12 },
  btn: { marginTop: 10, alignSelf: "flex-start", backgroundColor: colors.ink, paddingHorizontal: 12, paddingVertical: 6, borderRadius: btnRadius },
  btnText: { color: colors.white, fontWeight: "700" },
});
