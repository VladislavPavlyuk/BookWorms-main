import { useCallback, useState } from "react";
import {
  Alert,
  FlatList,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, ShelfApi } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { HistoryLink } from "../../src/HistoryLink";
import { colors, btnRadius } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
import type { Shelf } from "../../src/types";

export default function ShelfScreen() {
  const router = useRouter();
  const [shelves, setShelves] = useState<Shelf[]>([]);
  const [pending, setPending] = useState<Shelf[]>([]);
  const [lentOutCount, setLentOutCount] = useState(0);
  const [isbn, setIsbn] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [ageShelf, setAgeShelf] = useState<Shelf | null>(null);
  const [ageMin, setAgeMin] = useState("0");
  const [ageMax, setAgeMax] = useState("18");
  const [manual, setManual] = useState({
    isbn: "",
    title: "",
    authors: "",
    publisher: "",
    publish_date: "",
  });

  const load = async () => {
    const data = await ShelfApi.mine();
    setShelves(Array.isArray(data?.shelves) ? data.shelves : []);
    setPending(Array.isArray(data?.pending_returns) ? data.pending_returns : []);
    setLentOutCount(Number(data?.lent_out_count) || 0);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e)));
    }, [])
  );

  const addIsbn = async () => {
    try {
      await ShelfApi.addIsbn(isbn.trim());
      setIsbn("");
      await load();
    } catch (e) {
      Alert.alert("ISBN", e instanceof ApiError ? e.message : String(e));
    }
  };

  const addManual = async () => {
    try {
      await ShelfApi.addManual(manual);
      setManualOpen(false);
      setManual({ isbn: "", title: "", authors: "", publisher: "", publish_date: "" });
      await load();
    } catch (e) {
      Alert.alert("Вручну", e instanceof ApiError ? e.message : String(e));
    }
  };

  const saveAge = async () => {
    if (!ageShelf) return;
    try {
      await ShelfApi.readerAge(ageShelf.id, Number(ageMin), Number(ageMax));
      setAgeShelf(null);
      await load();
    } catch (e) {
      Alert.alert("Вік", e instanceof ApiError ? e.message : String(e));
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
      Alert.alert("Повернення", "Підтверджено.");
      await load();
    } catch (e) {
      Alert.alert("Повернення", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.screen }}>
      <View style={styles.row}>
        <CyrillicTextInput
          placeholder="ISBN 10/13"
          placeholderTextColor={colors.muted}
          style={styles.input}
          value={isbn}
          onChangeText={setIsbn}
          autoCapitalize="none"
        />
        <Pressable style={styles.add} onPress={addIsbn}>
          <Text style={styles.addText}>ISBN</Text>
        </Pressable>
        <Pressable
          style={[styles.add, { backgroundColor: colors.stamp }]}
          onPress={() => setManualOpen(true)}
          accessibilityRole="button"
          accessibilityLabel="Додати книгу вручну"
        >
          <Text style={styles.addText}>Вручну</Text>
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
          <View>
            <Text style={styles.physHint}>
              На полиці — лише те, що фізично у вас: власні вільні та позичені (з власником і терміном).
              Видані вами в позику з’являються на полиці позичальника.
              {lentOutCount > 0
                ? ` Зараз у позиці з ваших: ${lentOutCount} — див. Date Due Slip.`
                : ""}
            </Text>
            {lentOutCount > 0 ? (
              <Pressable onPress={() => router.push("/(tabs)/slips")} style={styles.slipsLink}>
                <Text style={styles.link}>Відкрити Date Due Slip</Text>
              </Pressable>
            ) : null}
            {pending.length ? (
              <View style={styles.pendingBox}>
                <Text style={styles.sec}>Підтвердити повернення ({pending.length})</Text>
                <Text style={styles.pendingHint}>
                  Позичальник повідомив про повернення. Підтвердіть, коли книга у вас.
                </Text>
                {pending.map((s) => (
                  <View key={s.id} style={[styles.card, styles.pendingCard]}>
                    <BookCover uri={s.book.cover_url} size="full" bleed={0} />
                    <View style={styles.cardBody}>
                      <Text style={styles.title}>{s.book.title}</Text>
                      <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center" }}>
                        <Text style={styles.meta}>від </Text>
                        <UserNameLink user={s.user} style={styles.meta} />
                      </View>
                      <Pressable style={styles.confirmBtn} onPress={() => confirm(s)}>
                        <Text style={styles.confirmBtnText}>Підтвердити повернення</Text>
                      </Pressable>
                    </View>
                  </View>
                ))}
              </View>
            ) : null}
          </View>
        }
        contentContainerStyle={{ paddingBottom: 24 }}
        ListEmptyComponent={
          <Text style={styles.empty}>На полиці ще немає примірників. Додайте ISBN вище.</Text>
        }
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Pressable onPress={() => router.push(`/book/${item.book.id}`)}>
              <BookCover uri={item.book.cover_url} size="full" bleed={0} />
              <View style={styles.cardBody}>
                <Text style={styles.title}>{item.book.title}</Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center" }}>
                  <Text style={styles.meta}>
                    {item.copy_id ? `Примірник #${item.copy_id} · ` : ""}
                    {item.book.authors}
                  </Text>
                  {item.borrowed_from ? (
                    <>
                      <Text style={styles.meta}> · позичено у </Text>
                      <UserNameLink user={item.borrowed_from} style={styles.meta} />
                    </>
                  ) : (
                    <Text style={styles.meta}> · власна</Text>
                  )}
                  <Text
                    style={[
                      styles.meta,
                      item.is_overdue ? { color: colors.stamp, fontWeight: "700" } : null,
                    ]}
                  >
                    {item.due_date ? ` · до ${item.due_date}` : ""}
                    {item.is_overdue
                      ? " · прострочено"
                      : item.days_left != null
                        ? ` · ще ${item.days_left} дн.`
                        : ""}
                    {item.return_pending ? " · очікує підтвердження" : ""}
                    {` · ${item.book.reader_age_summary}`}
                  </Text>
                </View>
              </View>
            </Pressable>
            <View style={[styles.actions, styles.cardBody]}>
              <HistoryLink copyId={item.copy_id} style={styles.link} />
              {item.borrowed_from && (
                <Pressable onPress={() => router.push(`/chat/${item.borrowed_from!.id}`)}>
                  <Text style={styles.link}>Чат з власником</Text>
                </Pressable>
              )}
              {!item.borrowed_from && (
                <Pressable
                  onPress={() => {
                    setAgeMin(String(item.book.min_readers_age));
                    setAgeMax(String(item.book.max_readers_age));
                    setAgeShelf(item);
                  }}
                >
                  <Text style={styles.link}>Вік читача</Text>
                </Pressable>
              )}
              <Pressable
                onPress={() =>
                  router.push({ pathname: "/post/new", params: { book_id: String(item.book.id) } })
                }
              >
                <Text style={styles.link}>Пост</Text>
              </Pressable>
              <Pressable onPress={() => act(item)}>
                <Text style={styles.action}>
                  {item.borrowed_from ? "Повернути" : "Прибрати"}
                </Text>
              </Pressable>
            </View>
          </View>
        )}
      />

      <Modal visible={manualOpen} animationType="slide" onRequestClose={() => setManualOpen(false)}>
        <ScrollView style={{ flex: 1, backgroundColor: colors.screen }} contentContainerStyle={{ padding: 20, paddingTop: 56 }}>
          <Text style={styles.modalH}>Додати книгу вручну</Text>
          {(["isbn", "title", "authors", "publisher", "publish_date"] as const).map((k) => (
            <CyrillicTextInput
              key={k}
              placeholder={k}
              placeholderTextColor={colors.muted}
              style={styles.inputFull}
              value={manual[k]}
              onChangeText={(v) => setManual((m) => ({ ...m, [k]: v }))}
              autoCapitalize="none"
            />
          ))}
          <Pressable style={styles.btn} onPress={addManual}>
            <Text style={styles.addText}>Зберегти</Text>
          </Pressable>
          <Pressable style={[styles.btn, { backgroundColor: colors.muted, marginTop: 8 }]} onPress={() => setManualOpen(false)}>
            <Text style={styles.addText}>Закрити</Text>
          </Pressable>
        </ScrollView>
      </Modal>

      <Modal visible={!!ageShelf} transparent animationType="fade" onRequestClose={() => setAgeShelf(null)}>
        <View style={styles.backdrop}>
          <View style={styles.sheet}>
            <Text style={styles.modalH}>Рекомендований вік</Text>
            <Text style={styles.meta}>{ageShelf?.book.title}</Text>
            <View style={styles.row}>
              <TextInput style={styles.age} keyboardType="number-pad" value={ageMin} onChangeText={setAgeMin} />
              <Text style={{ color: colors.ink, alignSelf: "center" }}>–</Text>
              <TextInput style={styles.age} keyboardType="number-pad" value={ageMax} onChangeText={setAgeMax} />
            </View>
            <Text style={styles.meta}>0–18 (18 = 18+)</Text>
            <Pressable style={styles.btn} onPress={saveAge}>
              <Text style={styles.addText}>Зберегти</Text>
            </Pressable>
            <Pressable onPress={() => setAgeShelf(null)}>
              <Text style={[styles.link, { marginTop: 12, textAlign: "center" }]}>Скасувати</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", padding: 12, gap: 8 },
  empty: { color: colors.muted, textAlign: "center", marginTop: 40, paddingHorizontal: 24 },
  physHint: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 16,
    paddingHorizontal: 16,
    paddingTop: 4,
    paddingBottom: 8,
  },
  slipsLink: { paddingHorizontal: 16, marginBottom: 10 },
  input: { flex: 1, borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, paddingVertical: 8 },
  inputFull: { borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, paddingVertical: 10, marginBottom: 12 },
  add: { backgroundColor: colors.ink, paddingHorizontal: 12, justifyContent: "center", borderRadius: btnRadius },
  addText: { color: colors.white, fontWeight: "700", textAlign: "center" },
  sec: { color: colors.stamp, fontWeight: "700", marginBottom: 8 },
  pendingBox: { marginBottom: 12 },
  pendingHint: { color: colors.muted, fontSize: 12, marginBottom: 10, lineHeight: 16 },
  pendingCard: { borderColor: colors.stampOk, backgroundColor: "#E8F5E9" },
  confirmBtn: {
    marginTop: 10,
    backgroundColor: colors.stampOk,
    paddingVertical: 10,
    paddingHorizontal: 12,
    alignSelf: "stretch",
    borderRadius: btnRadius,
  },
  confirmBtnText: { color: "#fff", fontWeight: "800", textAlign: "center" },
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
  cardBody: { paddingHorizontal: 16, paddingVertical: 10 },
  title: { color: colors.ink, fontWeight: "700", fontSize: 16 },
  meta: { color: colors.muted, marginTop: 4, fontSize: 13 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 14, marginTop: 10 },
  link: { color: colors.ink, fontWeight: "700" },
  action: { color: colors.stamp, fontWeight: "700" },
  modalH: { fontSize: 20, fontWeight: "800", color: colors.ink, marginBottom: 12 },
  btn: { backgroundColor: colors.ink, padding: 14, marginTop: 8, borderRadius: btnRadius },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.35)", justifyContent: "center", padding: 24 },
  sheet: { backgroundColor: colors.paper, padding: 20 },
  age: { flex: 1, borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, textAlign: "center", fontSize: 20, paddingVertical: 8 },
});
