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
import type { Shelf } from "../../src/types";

export default function Browse() {
  const router = useRouter();
  const [others, setOthers] = useState<Shelf[]>([]);
  const [myOwned, setMyOwned] = useState<Shelf[]>([]);
  const [target, setTarget] = useState<Shelf | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const data = await BrowseApi.list();
    setOthers(data.others);
    setMyOwned(data.my_owned);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Каталог", e instanceof ApiError ? e.message : String(e)));
    }, [])
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.screen }}>
      <FlatList
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
        contentContainerStyle={{ paddingBottom: 24 }}
        ListEmptyComponent={<Text style={styles.empty}>Немає чужих книг</Text>}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Pressable onPress={() => router.push(`/user/${item.user.id}`)}>
              <Text style={styles.owner}>{item.user.username}</Text>
            </Pressable>
            <Pressable onPress={() => router.push(`/book/${item.book.id}`)}>
              <BookCover uri={item.book.cover_url} size="full" bleed={0} />
              <View style={styles.cardBody}>
                <Text style={styles.title}>{item.book.title}</Text>
                <Text style={styles.meta}>
                  {item.book.authors} · {item.book.reader_age_summary}
                </Text>
              </View>
            </Pressable>
            <Pressable style={[styles.btn, styles.cardBody]} onPress={() => setTarget(item)}>
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
  coverFull: { borderWidth: 0 },
  cardBody: { paddingHorizontal: 16, paddingBottom: 12 },
  owner: { color: colors.stamp, fontWeight: "700", marginBottom: 0, paddingHorizontal: 16, paddingTop: 12 },
  title: { color: colors.ink, fontWeight: "700", fontSize: 16 },
  meta: { color: colors.muted, marginTop: 4 },
  btn: { marginTop: 10, alignSelf: "flex-start", backgroundColor: colors.ink, paddingHorizontal: 12, paddingVertical: 6 },
  btnText: { color: colors.white, fontWeight: "700" },
});
