import { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, BrowseApi, MsgApi } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { HistoryLink } from "../../src/HistoryLink";
import { RequestModal } from "../../src/RequestModal";
import { useAuth } from "../../src/auth";
import { colors } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
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
    const uid = Number(id);
    if (user && uid === user.id) {
      router.replace("/(tabs)/more");
      return;
    }
    load().catch((e) =>
      Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e))
    );
  }, [id, user?.id]);

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

  const requestCopy = (s: Shelf) => {
    const rid = s.request_shelf_id;
    if (!rid) {
      Alert.alert("Запит", "Немає рядка власника для цього примірника.");
      return;
    }
    if (s.borrowed_from) {
      setTarget({
        ...s,
        id: rid,
        user: s.borrowed_from,
        borrowed_from: null,
        is_lent_out: true,
        lent_to: owner,
        loan_due_date: s.due_date,
        request_shelf_id: rid,
      });
      return;
    }
    setTarget(s);
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.screen }}
      contentContainerStyle={{ paddingBottom: 24 }}
    >
      <Text style={styles.h}>{owner?.username}</Text>
      <Text style={styles.bio}>{owner?.biography || "—"}</Text>
      <Text style={styles.hint}>
        Лише те, що фізично у цього користувача (власне вільне або позичене з власником і терміном).
      </Text>
      {!isOwn && user && (
        <Pressable onPress={openChat} style={styles.chatBtn}>
          <Text style={styles.chatBtnText}>
            {canChat ? "Написати повідомлення" : "Чат (потрібен спільний запит)"}
          </Text>
        </Pressable>
      )}

      <Text style={styles.sec}>На полиці зараз</Text>
      {shelves.length === 0 ? (
        <Text style={styles.empty}>Зараз нічого немає на цій полиці.</Text>
      ) : (
        shelves.map((s) => (
          <View key={s.id} style={styles.card}>
            <Pressable onPress={() => router.push(`/book/${s.book.id}`)}>
              <BookCover uri={s.book.cover_url} size="full" bleed={0} />
              <View style={styles.cardBody}>
                <Text style={styles.title}>{s.book.title}</Text>
                <View style={styles.metaRow}>
                  {s.borrowed_from ? (
                    <>
                      <Text style={[styles.meta, styles.warn]}>позика · власник </Text>
                      <UserNameLink user={s.borrowed_from} style={styles.meta} />
                      {!!s.due_date && (
                        <Text
                          style={[
                            styles.meta,
                            s.is_overdue ? { color: colors.stamp, fontWeight: "700" } : null,
                          ]}
                        >
                          {` · до ${s.due_date}`}
                          {s.is_overdue
                            ? " · прострочено"
                            : s.days_left != null
                              ? ` · ще ${s.days_left} дн.`
                              : ""}
                        </Text>
                      )}
                    </>
                  ) : (
                    <Text style={styles.meta}>власний · вільний</Text>
                  )}
                  <Text style={styles.meta}>{` · ${s.book.reader_age_summary}`}</Text>
                </View>
              </View>
            </Pressable>
            <View style={styles.cardBody}>
              <HistoryLink copyId={s.copy_id} style={{ marginBottom: 8 }} />
              {!isOwn && user && (
                <Pressable onPress={() => requestCopy(s)}>
                  <Text style={styles.act}>
                    {s.borrowed_from ? "Просити передачу у власника" : "Позичити / обмін"}
                  </Text>
                </Pressable>
              )}
            </View>
          </View>
        ))
      )}

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
  h: { fontSize: 22, fontWeight: "800", color: colors.ink, paddingHorizontal: 16, paddingTop: 12 },
  bio: { color: colors.muted, marginBottom: 8, paddingHorizontal: 16 },
  hint: { color: colors.muted, fontSize: 12, lineHeight: 16, paddingHorizontal: 16, marginBottom: 12 },
  sec: {
    fontWeight: "800",
    color: colors.ink,
    paddingHorizontal: 16,
    marginTop: 8,
    marginBottom: 8,
    fontSize: 16,
  },
  empty: { color: colors.muted, paddingHorizontal: 16, marginBottom: 8 },
  chatBtn: {
    borderWidth: 1,
    borderColor: colors.stamp,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginBottom: 16,
    marginHorizontal: 16,
    alignSelf: "flex-start",
  },
  chatBtnText: { color: colors.stamp, fontWeight: "800" },
  card: {
    borderWidth: 0,
    borderBottomWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 0,
    marginBottom: 0,
    overflow: "hidden",
  },
  cardBody: { paddingHorizontal: 16, paddingBottom: 12, paddingTop: 10 },
  title: { fontWeight: "700", color: colors.ink },
  metaRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", marginTop: 4 },
  meta: { color: colors.muted },
  warn: { color: colors.stamp, fontWeight: "700" },
  act: { color: colors.stamp, fontWeight: "800", marginTop: 8 },
});
