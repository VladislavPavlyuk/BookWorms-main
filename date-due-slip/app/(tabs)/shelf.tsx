import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  FlatList,
  Image,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, ShelfApi } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { HistoryLink } from "../../src/HistoryLink";
import { IsbnScanModal, isbnReadyToAdd, normalizeIsbn } from "../../src/IsbnScanModal";
import { BookCoverCaptureModal } from "../../src/BookCoverCaptureModal";
import { colors, btnRadius } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
import type { BookPriceEval, BookPriceQuote, Shelf } from "../../src/types";

const MAX_MANUAL_PHOTOS = 8;

type ManualPhoto = { uri: string; name: string; type: string };

export default function ShelfScreen() {
  const router = useRouter();
  const [shelves, setShelves] = useState<Shelf[]>([]);
  const [pending, setPending] = useState<Shelf[]>([]);
  const [lentOutCount, setLentOutCount] = useState(0);
  const [priceTotal, setPriceTotal] = useState("0.00");
  const [sourcesOpen, setSourcesOpen] = useState<BookPriceQuote[] | null>(null);
  const [isbn, setIsbn] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [editShelfId, setEditShelfId] = useState<number | null>(null);
  const [existingPhotoUrls, setExistingPhotoUrls] = useState<{ id?: number; uri: string }[]>([]);
  const [deletePhotoIds, setDeletePhotoIds] = useState<number[]>([]);
  const [scanOpen, setScanOpen] = useState(false);
  const [coverCamOpen, setCoverCamOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [ageShelf, setAgeShelf] = useState<Shelf | null>(null);
  const [ageMin, setAgeMin] = useState("0");
  const [ageMax, setAgeMax] = useState("18");
  const [manual, setManual] = useState({
    isbn: "",
    title: "",
    authors: "",
    publisher: "",
    publish_date: "",
    cover_text: "",
  });
  const [manualPhotos, setManualPhotos] = useState<ManualPhoto[]>([]);
  const [aiStatus, setAiStatus] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const lastAutoRef = useRef("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = async () => {
    const data = await ShelfApi.mine();
    setShelves(Array.isArray(data?.shelves) ? data.shelves : []);
    setPending(Array.isArray(data?.pending_returns) ? data.pending_returns : []);
    setLentOutCount(Number(data?.lent_out_count) || 0);
    setPriceTotal(data?.price_total_uah || "0.00");
  };

  const refreshPrice = async (bookId: number) => {
    try {
      const r = await ShelfApi.refreshPrice(bookId);
      setShelves((prev) =>
        prev.map((s) =>
          s.book.id === bookId ? { ...s, price_eval: r.price_eval as BookPriceEval } : s
        )
      );
      Alert.alert("Ціна", "Оновлення оцінки запущено. Оновіть полицю за хвилину.");
      setTimeout(() => {
        load().catch(() => undefined);
      }, 2500);
    } catch (e) {
      Alert.alert("Ціна", e instanceof ApiError ? e.message : String(e));
    }
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e)));
    }, [])
  );

  const addIsbn = useCallback(async (raw?: string) => {
    const code = (raw ?? isbn).trim();
    const norm = normalizeIsbn(code);
    if (!norm) {
      if (code) Alert.alert("ISBN", "Потрібен повний ISBN (10 або 13 символів).");
      return;
    }
    if (adding) return;
    if (norm === lastAutoRef.current) return;
    lastAutoRef.current = norm;
    setAdding(true);
    try {
      await ShelfApi.addIsbn(norm);
      setIsbn("");
      lastAutoRef.current = "";
      await load();
    } catch (e) {
      lastAutoRef.current = "";
      Alert.alert("ISBN", e instanceof ApiError ? e.message : String(e));
    } finally {
      setAdding(false);
    }
  }, [adding, isbn]);

  const onIsbnChange = (text: string) => {
    setIsbn(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const ready = isbnReadyToAdd(text.trim());
    if (!ready) return;
    debounceRef.current = setTimeout(() => {
      void addIsbn(ready);
    }, 450);
  };

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const onScannedIsbn = async (code: string) => {
    setScanOpen(false);
    setIsbn(code);
    lastAutoRef.current = "";
    await addIsbn(code);
  };

  const resetManualForm = () => {
    setManual({ isbn: "", title: "", authors: "", publisher: "", publish_date: "", cover_text: "" });
    setManualPhotos([]);
    setAiStatus("");
    setEditShelfId(null);
    setExistingPhotoUrls([]);
    setDeletePhotoIds([]);
  };

  const openEditManual = (item: Shelf) => {
    const b = item.book;
    const local = b.isbn?.startsWith("9799");
    setManual({
      isbn: local ? "" : b.isbn || "",
      title: b.title || "",
      authors: b.authors || "",
      publisher: b.publisher || "",
      publish_date: b.publish_date || "",
      cover_text: b.cover_text || "",
    });
    setManualPhotos([]);
    setDeletePhotoIds([]);
    const urls = (b.photo_urls || []).map((uri) => ({ uri }));
    setExistingPhotoUrls(urls);
    setEditShelfId(item.id);
    setAiStatus("");
    setManualOpen(true);
  };

  const addManual = async () => {
    const title = (manual.title || "").trim();
    const isbnVal = (manual.isbn || "").trim();
    if (!title && manualPhotos.length === 0 && !editShelfId) {
      Alert.alert("Вручну", "Вкажіть назву або зробіть хоча б одне фото обкладинки.");
      return;
    }
    try {
      if (editShelfId) {
        await ShelfApi.updateManual(editShelfId, {
          isbn: isbnVal,
          title: title || undefined,
          authors: manual.authors || undefined,
          publisher: manual.publisher || undefined,
          publish_date: manual.publish_date || undefined,
          cover_text: manual.cover_text || undefined,
          photos: manualPhotos,
          delete_photo_ids: deletePhotoIds.length ? deletePhotoIds : undefined,
        });
      } else {
        await ShelfApi.addManual({
          isbn: isbnVal || undefined,
          title: title || undefined,
          authors: manual.authors || undefined,
          publisher: manual.publisher || undefined,
          publish_date: manual.publish_date || undefined,
          cover_text: manual.cover_text || undefined,
          photos: manualPhotos,
        });
      }
      setManualOpen(false);
      resetManualForm();
      await load();
    } catch (e) {
      Alert.alert(
        editShelfId ? "Редагування" : "Вручну",
        e instanceof ApiError ? e.message : String(e)
      );
    }
  };

  const recognizeFromPhotos = async (photos?: ManualPhoto[]) => {
    const list = photos && photos.length ? photos : manualPhotos;
    if (!list.length) {
      setAiStatus("Спочатку зробіть фото обкладинки.");
      return;
    }
    setAiBusy(true);
    setAiStatus(
      list.length > 1
        ? `AI читає всі ${list.length} фото…`
        : "AI розпізнає обкладинку…"
    );
    try {
      const data = await ShelfApi.recognizeCover(list);
      const titleGuess =
        (data.title || "").trim() ||
        (data.raw_text || "").split("\n").map((s) => s.trim()).find(Boolean) ||
        "";
      const coverDump = (data.cover_text || data.raw_text || "").trim();
      setManual((m) => ({
        isbn: m.isbn.trim() ? m.isbn : data.isbn || "",
        title: m.title.trim() ? m.title : titleGuess,
        authors: m.authors.trim() ? m.authors : data.authors || "",
        publisher: m.publisher.trim() ? m.publisher : data.publisher || "",
        publish_date: m.publish_date.trim() ? m.publish_date : data.publish_date || "",
        cover_text: coverDump || m.cover_text,
      }));
      const bits: string[] = [];
      if (titleGuess) bits.push("назва");
      if (data.authors) bits.push("автори");
      if (data.isbn) bits.push("ISBN");
      else if (data.isbn_missing || data.note) bits.push(data.note || "ISBN code not exists");
      if (coverDump) bits.push("повний текст");
      const n = data.photos_scanned || list.length;
      const extra =
        n > 1
          ? ` (краще з ${(data.best_photo_index ?? 0) + 1}/${n})`
          : "";
      setAiStatus(
        bits.length ? `AI заповнив: ${bits.join(", ")}${extra}` : "AI не знайшов текст на обкладинці"
      );
    } catch (e) {
      setAiStatus(e instanceof ApiError ? e.message : String(e));
    } finally {
      setAiBusy(false);
    }
  };

  const takeManualPhoto = () => {
    if (manualPhotos.length >= MAX_MANUAL_PHOTOS) {
      Alert.alert("Фото", `Максимум ${MAX_MANUAL_PHOTOS} фото.`);
      return;
    }
    setCoverCamOpen(true);
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
          placeholder={adding ? "Додаємо…" : "ISBN 10/13 — додається сам"}
          placeholderTextColor={colors.muted}
          style={styles.isbnInput}
          value={isbn}
          onChangeText={onIsbnChange}
          autoCapitalize="none"
          keyboardType="number-pad"
          maxLength={13}
          editable={!adding}
        />
        <Pressable
          style={[styles.add, styles.scanBtn]}
          onPress={() => setScanOpen(true)}
          accessibilityRole="button"
          accessibilityLabel="Сканувати ISBN камерою"
        >
          <Ionicons name="camera" size={22} color={colors.white} />
        </Pressable>
        <Pressable
          style={[styles.add, { backgroundColor: colors.stamp }]}
          onPress={() => {
            resetManualForm();
            setManualOpen(true);
          }}
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
            <View style={styles.priceTotalBox}>
              <Text style={styles.priceTotalLabel}>Оцінка вартості полиці</Text>
              <Text style={styles.priceTotalValue}>≈ {priceTotal} ₴</Text>
              <Text style={styles.priceTotalHint}>сума оцінок ISBN (≥3 джерела)</Text>
            </View>
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
        renderItem={({ item }) => {
          const coverUri =
            item.book.cover_url ||
            (item.book.photo_urls && item.book.photo_urls[0]) ||
            null;
          const extras = item.book.photo_urls || [];
          return (
          <View style={styles.card}>
            <Pressable onPress={() => router.push(`/book/${item.book.id}`)}>
              <BookCover uri={coverUri} size="full" bleed={0} />
              {extras.length > 0 ? (
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.shelfPhotoStrip}
                >
                  {extras.map((u, i) => (
                    <Image key={`${u}-${i}`} source={{ uri: u }} style={styles.shelfPhotoThumb} />
                  ))}
                </ScrollView>
              ) : null}
              <View style={styles.cardBody}>
                <Text style={styles.title}>{item.book.title}</Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center" }}>
                  <Text style={styles.meta}>
                    {item.copy_id ? `Примірник #${item.copy_id} · ` : ""}
                    {item.book.isbn?.startsWith("9799") || item.book.isbn_missing
                      ? item.book.note || "ISBN code not exists"
                      : item.book.isbn
                        ? `ISBN ${item.book.isbn}`
                        : ""}
                    {item.book.authors ? ` · ${item.book.authors}` : ""}
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
                {item.price_eval?.status === "ready" && item.price_eval.price_avg ? (
                  <View style={styles.priceRow}>
                    <Text style={styles.priceAvg}>
                      ≈ {item.price_eval.price_avg} ₴
                      <Text style={styles.meta}>
                        {" "}
                        ({item.price_eval.price_min}–{item.price_eval.price_max})
                      </Text>
                    </Text>
                    <View style={styles.priceActions}>
                      <Pressable
                        onPress={() => setSourcesOpen(item.price_eval?.quotes || [])}
                        style={styles.priceBtn}
                      >
                        <Text style={styles.priceBtnText}>
                          Price sources ({item.price_eval.source_count})
                        </Text>
                      </Pressable>
                      <Pressable onPress={() => refreshPrice(item.book.id)} style={styles.priceBtn}>
                        <Text style={styles.priceBtnText}>Оновити</Text>
                      </Pressable>
                    </View>
                  </View>
                ) : (
                  <View style={styles.priceRow}>
                    <Text style={styles.meta}>
                      {item.price_eval?.status === "pending"
                        ? "Оцінка ціни…"
                        : item.price_eval?.status === "missing"
                          ? "Ціну не знайдено"
                          : "Ціна ще не оцінена"}
                    </Text>
                    <Pressable onPress={() => refreshPrice(item.book.id)} style={styles.priceBtn}>
                      <Text style={styles.priceBtnText}>
                        {item.price_eval ? "Оновити ціну" : "Оцінити ціну"}
                      </Text>
                    </Pressable>
                  </View>
                )}
              </View>
            </Pressable>
            <View style={[styles.actions, styles.cardBody]}>
              <HistoryLink copyId={item.copy_id} style={styles.link} />
              {item.borrowed_from && (
                <Pressable onPress={() => router.push(`/chat/${item.borrowed_from!.id}`)}>
                  <Text style={styles.link}>Чат з власником</Text>
                </Pressable>
              )}
              {!item.borrowed_from && item.can_edit_manual && (
                <Pressable
                  onPress={() => openEditManual(item)}
                  accessibilityRole="button"
                  accessibilityLabel="Редагувати"
                  hitSlop={8}
                >
                  <Ionicons name="create-outline" size={22} color={colors.ink} />
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
          );
        }}
      />

      <Modal
        visible={manualOpen}
        animationType="slide"
        onRequestClose={() => {
          setManualOpen(false);
          resetManualForm();
        }}
      >
        <ScrollView style={{ flex: 1, backgroundColor: colors.screen }} contentContainerStyle={{ padding: 20, paddingTop: 56 }}>
          <Text style={styles.modalH}>{editShelfId ? "Редагувати книгу" : "Додати книгу вручну"}</Text>
          <Text style={[styles.physHint, { paddingHorizontal: 0, marginBottom: 12 }]}>
            ISBN не обов’язковий. Після знімка AI заповнить порожні поля (назва / автори / ISBN).
          </Text>
          {(
            [
              ["isbn", "ISBN (необов’язково)"],
              ["title", "Назва"],
              ["authors", "Автори"],
              ["publisher", "Видавець"],
              ["publish_date", "Дата видання"],
            ] as const
          ).map(([k, ph]) => (
            <CyrillicTextInput
              key={k}
              placeholder={ph}
              placeholderTextColor={colors.muted}
              style={styles.inputFull}
              value={manual[k]}
              onChangeText={(v) => setManual((m) => ({ ...m, [k]: v }))}
              autoCapitalize="none"
            />
          ))}
          <Text style={[styles.sec, { marginTop: 8 }]}>Текст з обкладинки (AI)</Text>
          <CyrillicTextInput
            placeholder="Після знімка тут з’явиться весь розпізнаний текст"
            placeholderTextColor={colors.muted}
            style={[styles.inputFull, { minHeight: 140, textAlignVertical: "top" }]}
            value={manual.cover_text}
            onChangeText={(v) => setManual((m) => ({ ...m, cover_text: v }))}
            multiline
            autoCapitalize="sentences"
          />
          <Text style={[styles.sec, { marginTop: 8 }]}>Фото книги</Text>
          <Text style={[styles.physHint, { paddingHorizontal: 0 }]}>
            Камера зніме обкладинку в рамці і обріже фон. До {MAX_MANUAL_PHOTOS}. AI заповнить поля автоматично.
          </Text>
          {existingPhotoUrls.length > 0 ? (
            <View style={styles.photoRow}>
              {existingPhotoUrls.map((p, i) => (
                <View key={`ex-${p.uri}-${i}`} style={styles.photoThumb}>
                  <Image source={{ uri: p.uri }} style={styles.photoImg} />
                </View>
              ))}
            </View>
          ) : null}
          <View style={styles.photoActions}>
            <Pressable
              style={[styles.add, styles.scanBtn, styles.camOnlyBtn]}
              onPress={takeManualPhoto}
              accessibilityRole="button"
              accessibilityLabel="Зняти фото книги"
            >
              <Ionicons name="camera" size={22} color={colors.white} />
            </Pressable>
            <Pressable
              style={[styles.add, { backgroundColor: colors.stamp }, aiBusy && { opacity: 0.5 }]}
              onPress={() => {
                void recognizeFromPhotos();
              }}
              disabled={aiBusy || manualPhotos.length === 0}
              accessibilityRole="button"
              accessibilityLabel="AI розпізнати"
            >
              <Text style={styles.addText}>{aiBusy ? "AI…" : "AI розпізнати"}</Text>
            </Pressable>
            {manualPhotos.length > 0 ? (
              <Text style={styles.photoCount}>
                {manualPhotos.length} / {MAX_MANUAL_PHOTOS}
              </Text>
            ) : null}
          </View>
          {aiStatus ? <Text style={[styles.physHint, { paddingHorizontal: 0 }]}>{aiStatus}</Text> : null}
          <View style={styles.photoRow}>
            {manualPhotos.map((p, i) => (
              <View key={`${p.uri}-${i}`} style={styles.photoThumb}>
                <Image source={{ uri: p.uri }} style={styles.photoImg} />
                <Pressable
                  style={styles.photoRemove}
                  onPress={() => setManualPhotos((prev) => prev.filter((_, j) => j !== i))}
                  accessibilityLabel="Видалити фото"
                >
                  <Text style={{ color: "#fff", fontWeight: "800" }}>×</Text>
                </Pressable>
              </View>
            ))}
          </View>
          <Pressable style={styles.btn} onPress={addManual}>
            <Text style={styles.addText}>{editShelfId ? "Оновити" : "Зберегти"}</Text>
          </Pressable>
          <Pressable
            style={[styles.btn, { backgroundColor: colors.stamp, marginTop: 8 }]}
            onPress={() => {
              const keepEdit = editShelfId;
              resetManualForm();
              if (keepEdit) setEditShelfId(keepEdit);
              setAiStatus("");
            }}
          >
            <Text style={styles.addText}>Очистити всі поля</Text>
          </Pressable>
          <Pressable
            style={[styles.btn, { backgroundColor: colors.muted, marginTop: 8 }]}
            onPress={() => {
              setManualOpen(false);
              resetManualForm();
            }}
          >
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

      <IsbnScanModal
        visible={scanOpen}
        onClose={() => setScanOpen(false)}
        onScan={onScannedIsbn}
      />
      <BookCoverCaptureModal
        visible={coverCamOpen}
        count={manualPhotos.length}
        onClose={() => setCoverCamOpen(false)}
        onCaptured={(photo) => {
          setManualPhotos((prev) => {
            if (prev.length >= MAX_MANUAL_PHOTOS) return prev;
            const next = [...prev, photo];
            if (next.length >= MAX_MANUAL_PHOTOS) {
              setTimeout(() => setCoverCamOpen(false), 0);
            }
            void recognizeFromPhotos(next);
            return next;
          });
        }}
      />

      <Modal
        visible={sourcesOpen != null}
        transparent
        animationType="fade"
        onRequestClose={() => setSourcesOpen(null)}
      >
        <View style={styles.backdrop}>
          <View style={styles.sheet}>
            <Text style={styles.modalH}>Price sources</Text>
            <ScrollView style={{ maxHeight: 360 }}>
              {(sourcesOpen || []).map((q, i) => (
                <View key={`${q.source_name}-${i}`} style={styles.sourceRow}>
                  <Text style={styles.sourceName}>{q.source_name}</Text>
                  <Text style={styles.sourcePrice}>
                    {q.price_uah} ₴
                    {q.currency !== "UAH" ? ` (${q.price} ${q.currency})` : ""}
                  </Text>
                </View>
              ))}
              {!sourcesOpen?.length ? (
                <Text style={styles.meta}>Немає збережених джерел.</Text>
              ) : null}
            </ScrollView>
            <Pressable onPress={() => setSourcesOpen(null)} style={{ marginTop: 12 }}>
              <Text style={[styles.link, { textAlign: "center" }]}>Закрити</Text>
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
  priceTotalBox: {
    marginHorizontal: 16,
    marginBottom: 10,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
  },
  priceTotalLabel: { color: colors.muted, fontSize: 12 },
  priceTotalValue: { color: colors.ink, fontSize: 20, fontWeight: "800", marginTop: 2 },
  priceTotalHint: { color: colors.muted, fontSize: 11, marginTop: 2 },
  priceRow: { marginTop: 8, gap: 6 },
  priceAvg: { color: colors.ink, fontWeight: "700", fontSize: 15 },
  priceActions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  priceBtn: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: btnRadius,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  priceBtnText: { color: colors.ink, fontWeight: "600", fontSize: 13 },
  sourceRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderColor: colors.line,
  },
  sourceName: { color: colors.ink, flex: 1, fontWeight: "600" },
  sourcePrice: { color: colors.ink, fontWeight: "700" },
  slipsLink: { paddingHorizontal: 16, marginBottom: 10 },
  input: { flex: 1, borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, paddingVertical: 8 },
  isbnInput: {
    width: 148,
    maxWidth: 148,
    flexGrow: 0,
    flexShrink: 0,
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: 8,
    fontSize: 16,
    fontVariant: ["tabular-nums"],
  },
  inputFull: { borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, paddingVertical: 10, marginBottom: 12 },
  add: { backgroundColor: colors.ink, paddingHorizontal: 12, justifyContent: "center", borderRadius: btnRadius, flexDirection: "row", alignItems: "center" },
  scanBtn: { backgroundColor: colors.fab },
  addText: { color: colors.white, fontWeight: "700", textAlign: "center" },
  photoActions: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 12 },
  camOnlyBtn: { paddingVertical: 10, paddingHorizontal: 14, minWidth: 48, justifyContent: "center" },
  photoCount: { color: colors.muted, fontWeight: "600" },
  photoRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 16 },
  photoThumb: { width: 72, height: 72, borderRadius: 8, overflow: "hidden", backgroundColor: colors.line },
  photoImg: { width: "100%", height: "100%" },
  photoRemove: {
    position: "absolute",
    top: 2,
    right: 2,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "rgba(0,0,0,0.65)",
    alignItems: "center",
    justifyContent: "center",
  },
  shelfPhotoStrip: { paddingHorizontal: 12, paddingVertical: 8, gap: 8 },
  shelfPhotoThumb: { width: 56, height: 56, borderRadius: 6, backgroundColor: colors.line },
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
