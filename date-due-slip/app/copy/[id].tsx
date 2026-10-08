import { useCallback, useState } from "react";
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, CopyApi } from "../../src/api";
import { useAuth } from "../../src/auth";
import { BookCover } from "../../src/BookCover";
import { htmlToPlain } from "../../src/htmlText";
import { colors, btnRadius } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
import type { BookCopyDetail, CopyEvent, QueueEntry, Shelf } from "../../src/types";

export default function CopyHistoryScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [copy, setCopy] = useState<BookCopyDetail | null>(null);
  const [holders, setHolders] = useState<Shelf[]>([]);
  const [events, setEvents] = useState<CopyEvent[]>([]);
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [myPos, setMyPos] = useState<number | null>(null);
  const [lent, setLent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const load = useCallback(async () => {
    const d = await CopyApi.history(Number(id));
    setCopy(d.copy);
    setHolders(d.holders);
    setEvents(d.events);
    setQueue(d.queue || []);
    setMyPos(d.my_queue_position ?? null);
    setLent(!!d.is_lent_out);
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      load().catch((e) =>
        Alert.alert("Історія", e instanceof ApiError ? e.message : String(e))
      );
    }, [load])
  );

  if (!copy) return null;
  const book = copy.book;
  const isOwner = user?.id === copy.owner.id;
  const canJoin = !!user && !isOwner && myPos == null;

  const join = async () => {
    setBusy(true);
    try {
      const r = await CopyApi.joinQueue(copy.id);
      Alert.alert("Черга", `Ви в черзі (позиція ${r.position}).`);
      await load();
    } catch (e) {
      Alert.alert("Черга", e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const leave = async () => {
    setBusy(true);
    try {
      await CopyApi.leaveQueue(copy.id);
      await load();
    } catch (e) {
      Alert.alert("Черга", e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const rotateQr = () => {
    Alert.alert(
      "Оновити QR-код?",
      "Стара наклейка перестане діяти. Роздрукуйте нову й прив’яжіть «Скан QR» на полиці.",
      [
        { text: "Скасувати", style: "cancel" },
        {
          text: "Оновити",
          style: "destructive",
          onPress: async () => {
            setBusy(true);
            try {
              await CopyApi.rotateQr(copy.id);
              await load();
              Alert.alert("QR", "Відв’язано. Роздрукуйте наклейки й відскануйте.", [
                { text: "Друк", onPress: () => router.push("/qr-print") },
                { text: "OK" },
              ]);
            } catch (e) {
              Alert.alert("QR", e instanceof ApiError ? e.message : String(e));
            } finally {
              setBusy(false);
            }
          },
        },
      ]
    );
  };

  const isbnRows = (
    [
      ["Видавець", book.publisher],
      ["Дата видання", book.publish_date],
      ["Палітурка", book.binding],
      ["Мова", book.language],
      ["Видання", book.edition],
      ["Сторінок", book.pages != null ? String(book.pages) : ""],
      ["Розміри", book.dimensions],
      ["Джерело", book.catalog_source || ""],
    ] as [string, string][]
  ).filter(([, v]) => !!(v && String(v).trim()));

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.screen }} contentContainerStyle={{ paddingBottom: 32 }}>
      <Pressable onPress={() => setInfoOpen(true)} accessibilityRole="button" accessibilityLabel="Деталі книги">
        <BookCover uri={book.cover_url} size="full" bleed={0} />
      </Pressable>
      <View style={styles.body}>
        <Text style={styles.copyTag}>Примірник #{copy.id}</Text>
        <Text style={styles.title} onPress={() => setInfoOpen(true)}>
          {book.title}
        </Text>
        <Text style={styles.meta}>{book.authors || "—"}</Text>
        <Text style={styles.meta}>ISBN {book.isbn}</Text>
        <View style={styles.row}>
          <Text style={styles.meta}>Власник: </Text>
          <UserNameLink user={copy.owner} style={styles.link} />
        </View>
        {lent ? <Text style={styles.lent}>Зараз у позиці</Text> : null}
        <Text style={styles.meta}>
          QR: {copy.qr_attached ? "приклеєно / прив’язано" : "ще не прив’язано"}
        </Text>

        {isOwner ? (
          <>
            <Text style={styles.h}>QR-наклейка</Text>
            <Text style={styles.meta}>
              Пізня прив’язка: друк не прив’язує код до книги. Наклейте наклейку → «Скан QR» у
              вікні опцій на полиці.
            </Text>
            <View style={styles.qActions}>
              {copy.qr_attached ? (
                <Pressable style={styles.btn} onPress={rotateQr} disabled={busy}>
                  <Text style={styles.btnText}>Оновити QR-код</Text>
                </Pressable>
              ) : null}
              <Pressable style={styles.btnGhost} onPress={() => router.push("/qr-print")}>
                <Text style={styles.btnGhostText}>Друк наклейок A4</Text>
              </Pressable>
            </View>
          </>
        ) : null}

        <Text style={styles.h}>Черга інтересу</Text>
        <Text style={styles.meta}>
          Якщо кілька людей хочуть цей примірник — FIFO. Після повернення наступний отримає
          автозапит; власник також може схвалити передачу третій особі з чату.
        </Text>
        {myPos != null ? (
          <Text style={styles.myPos}>Ваша позиція: {myPos}</Text>
        ) : null}
        <View style={styles.qActions}>
          {canJoin ? (
            <Pressable style={styles.btn} onPress={join} disabled={busy}>
              <Text style={styles.btnText}>Стати в чергу</Text>
            </Pressable>
          ) : null}
          {myPos != null ? (
            <Pressable style={styles.btnGhost} onPress={leave} disabled={busy}>
              <Text style={styles.btnGhostText}>Вийти з черги</Text>
            </Pressable>
          ) : null}
          {myPos != null ? (
            <Pressable
              style={styles.btnGhost}
              onPress={() => router.push(`/chat/${copy.owner.id}`)}
            >
              <Text style={styles.btnGhostText}>Чат з власником</Text>
            </Pressable>
          ) : null}
        </View>
        {queue.length === 0 ? (
          <Text style={styles.meta}>Черга порожня.</Text>
        ) : (
          queue.map((q) => (
            <View key={q.id} style={styles.card}>
              <Text style={styles.evCode}>
                #{q.position} · {q.username}
                {q.status === "offered" ? " · запропоновано" : ""}
              </Text>
            </View>
          ))
        )}

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

        <Text style={styles.h}>Де зараз (фізично)</Text>
        {holders.length === 0 ? (
          <Text style={styles.meta}>Ні на чиїй полиці.</Text>
        ) : (
          holders.map((s) => (
            <View key={s.id} style={styles.card}>
              <View style={styles.row}>
                <UserNameLink user={s.user} style={styles.link} />
                <Text style={styles.meta}>
                  {s.borrowed_from
                    ? ` · позика у ${s.borrowed_from.username}`
                    : " · власник · вільний"}
                </Text>
                {!!s.due_date && <Text style={styles.meta}>{` · до ${s.due_date}`}</Text>}
              </View>
            </View>
          ))
        )}
      </View>

      <Modal
        visible={infoOpen}
        animationType="slide"
        transparent
        onRequestClose={() => setInfoOpen(false)}
      >
        <View style={styles.infoBackdrop}>
          <View style={styles.infoCard}>
            <View style={styles.infoHeader}>
              <Text style={styles.infoTitle} numberOfLines={2}>
                {book.title}
              </Text>
              <Pressable onPress={() => setInfoOpen(false)} hitSlop={8}>
                <Text style={styles.infoClose}>Закрити</Text>
              </Pressable>
            </View>
            <ScrollView style={styles.infoScroll} nestedScrollEnabled>
              <BookCover uri={book.cover_url} size="md" />
              <Text style={styles.meta}>{book.authors || "—"}</Text>
              <Text style={styles.meta}>
                {book.isbn?.startsWith("9799") || book.isbn_missing
                  ? book.note || "ISBN code not exists"
                  : `ISBN ${book.isbn}${book.isbn10 ? ` · ${book.isbn10}` : ""}`}
              </Text>
              <Text style={[styles.h, { marginTop: 12 }]}>Дані ISBN</Text>
              {isbnRows.map(([k, v]) => (
                <Text key={k} style={styles.meta}>
                  <Text style={{ fontWeight: "700" }}>{k}: </Text>
                  {v}
                </Text>
              ))}
              {(book.subjects || []).length ? (
                <Text style={styles.meta}>
                  <Text style={{ fontWeight: "700" }}>Теми: </Text>
                  {(book.subjects || []).join(", ")}
                </Text>
              ) : null}
              {book.synopsis || book.overview ? (
                <View style={styles.proseWrap}>
                  <Text style={[styles.meta, { fontWeight: "700", marginBottom: 4 }]}>
                    {book.synopsis ? "Синопсис" : "Огляд"}
                  </Text>
                  <ScrollView style={styles.proseScroll} nestedScrollEnabled>
                    <Text style={styles.meta}>
                      {htmlToPlain(book.synopsis || book.overview)}
                    </Text>
                  </ScrollView>
                </View>
              ) : null}
              <Pressable
                style={[styles.btn, { marginTop: 16, alignSelf: "flex-start" }]}
                onPress={() => {
                  setInfoOpen(false);
                  router.push(`/book/${book.id}`);
                }}
              >
                <Text style={styles.btnText}>Усі примірники ISBN</Text>
              </Pressable>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  body: { paddingHorizontal: 16, paddingTop: 12 },
  copyTag: { color: colors.stamp, fontWeight: "800", letterSpacing: 0.5, marginBottom: 4 },
  title: { fontSize: 22, fontWeight: "800", color: colors.ink },
  meta: { color: colors.muted, marginTop: 2 },
  infoBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "flex-end",
  },
  infoCard: {
    backgroundColor: colors.white,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: "88%",
    paddingBottom: 24,
  },
  infoHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  infoTitle: { flex: 1, color: colors.ink, fontWeight: "800", fontSize: 18 },
  infoClose: { color: colors.stamp, fontWeight: "700" },
  infoScroll: { paddingHorizontal: 16, paddingTop: 12 },
  proseWrap: { marginTop: 10 },
  proseScroll: {
    maxHeight: 160,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    backgroundColor: "#F7F7F5",
  },
  lent: { color: colors.stamp, fontWeight: "700", marginTop: 8 },
  myPos: { color: colors.ink, fontWeight: "800", marginTop: 8 },
  link: { color: colors.stamp, fontWeight: "700" },
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", marginTop: 2 },
  h: { marginTop: 24, fontWeight: "800", color: colors.ink, marginBottom: 8 },
  qActions: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginVertical: 10 },
  btn: {
    backgroundColor: colors.stamp,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: btnRadius,
  },
  btnText: { color: "#fff", fontWeight: "800" },
  btnGhost: {
    borderWidth: 1,
    borderColor: colors.line,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: btnRadius,
  },
  btnGhostText: { color: colors.ink, fontWeight: "700" },
  card: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
    backgroundColor: colors.paper,
  },
  evCode: { fontWeight: "800", color: colors.ink },
  evTime: { color: colors.muted, fontSize: 12, marginTop: 2 },
});
