import { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, BrowseApi, MsgApi } from "../../src/api";
import { RequestModal } from "../../src/RequestModal";
import { useAuth } from "../../src/auth";
import { colors } from "../../src/theme";
import type { Shelf, User } from "../../src/types";

export default function UserShelf() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const router = useRouter();
  const [owner, setOwner] = useState<User | null>(null);
  const [shelves, setShelves] = useState<Shelf[]>([]);
  const [isOwn, setIsOwn] = useState(false);
  const [myOwned, setMyOwned] = useState<Shelf[]>([]);
  const [target, setTarget] = useState<Shelf | null>(null);
  const [canChat, setCanChat] = useState(false);

  const load = async () => {
    const uid = Number(id);
    const [d, browse, partners] = await Promise.all([
      BrowseApi.user(uid),
      BrowseApi.list(),
      MsgApi.partners().catch(() => [] as User[]),
    ]);
    setOwner(d.user);
    setShelves(d.shelves);
    setIsOwn(d.is_own);
    setMyOwned(browse.my_owned);
    setCanChat(!d.is_own && partners.some((p) => p.id === uid));
  };

  useEffect(() => {
    load().catch((e) =>
      Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e))
    );
  }, [id]);

  const openChat = () => {
    if (!owner) return;
    if (!canChat) {
      Alert.alert(
        "Чат",
        "Немає спільного запиту з цим користувачем. Спочатку позика або обмін — тоді з’явиться чат."
      );
      router.push("/exchanges");
      return;
    }
    router.push(`/chat/${owner.id}`);
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.screen }}
      contentContainerStyle={{ padding: 16 }}
    >
      <Text style={styles.h}>{owner?.username}</Text>
      <Text style={styles.bio}>{owner?.biography || "—"}</Text>
      {!isOwn && user && (
        <Pressable onPress={openChat} style={styles.chatBtn}>
          <Text style={styles.chatBtnText}>
            {canChat ? "Написати повідомлення" : "Чат (потрібен спільний запит)"}
          </Text>
        </Pressable>
      )}
      {shelves.map((s) => (
        <View key={s.id} style={styles.card}>
          <Pressable onPress={() => router.push(`/book/${s.book.id}`)}>
            <Text style={styles.title}>{s.book.title}</Text>
          </Pressable>
          <Text style={styles.meta}>
            {s.borrowed_from ? `позичено у ${s.borrowed_from.username}` : "власна"}
            {s.due_date ? ` · до ${s.due_date}` : ""}
            {` · ${s.book.reader_age_summary}`}
          </Text>
          {!isOwn && !s.borrowed_from && user && (
            <Pressable onPress={() => setTarget(s)}>
              <Text style={styles.act}>Позичити / обмін</Text>
            </Pressable>
          )}
          {!isOwn && !s.borrowed_from && (
            <Pressable
              onPress={() =>
                router.push({
                  pathname: "/post/new",
                  params: { book_id: String(s.book.id) },
                })
              }
            >
              <Text style={[styles.act, { color: colors.muted }]}>
                Написати пост (якщо книга у вас)
              </Text>
            </Pressable>
          )}
        </View>
      ))}
      <RequestModal
        target={target}
        myOwned={myOwned}
        onClose={() => setTarget(null)}
        onDone={load}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  h: { fontSize: 22, fontWeight: "800", color: colors.ink },
  bio: { color: colors.muted, marginBottom: 12 },
  chatBtn: {
    borderWidth: 1,
    borderColor: colors.stamp,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginBottom: 16,
    alignSelf: "flex-start",
  },
  chatBtnText: { color: colors.stamp, fontWeight: "800" },
  card: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 12,
    marginBottom: 8,
  },
  title: { fontWeight: "700", color: colors.ink },
  meta: { color: colors.muted, marginTop: 4 },
  act: { color: colors.stamp, fontWeight: "800", marginTop: 8 },
});
