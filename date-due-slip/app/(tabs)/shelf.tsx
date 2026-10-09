import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  FlatList,
  Image,
  ImageBackground,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, ShelfApi } from "../../src/api";
import { CameraGlyph } from "../../src/HeaderGlyphs";
import { IsbnScanModal, isbnReadyToAdd, normalizeIsbn } from "../../src/IsbnScanModal";
import { BookCoverCaptureModal } from "../../src/BookCoverCaptureModal";
import { BookIsbnInfoModal } from "../../src/BookIsbnInfoModal";
import {
  ShelfDetailActionBtn,
  ShelfInstanceDetailModal,
} from "../../src/ShelfInstanceDetailModal";
import { ShelfLogoChip } from "../../src/ShelfLogoChip";
import { ShelfCheckRow, ShelfRadioRow } from "../../src/ShelfSelectRow";
import { bookCoverFromDb, useResolvedMediaUrl } from "../../src/mediaUrl";
import { colors, btnRadius, fs, s } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
import type { BookPriceEval, BookPriceQuote, SaleGift, Shelf } from "../../src/types";
import { LISTING_CHECKBOX_OPTIONS, SALE_GIFT_OPTIONS } from "../../src/types";

const MAX_MANUAL_PHOTOS = 8;

type ManualPhoto = { uri: string; name: string; type: string };

/** Grid cover — resolves /media/... against API base (internal storage). */
function ShelfCoverImage({ uri }: { uri: string | null }) {
  const src = useResolvedMediaUrl(uri);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);
  if (!src || failed) {
    return (
      <View style={styles.coverMissing}>
        <Text style={styles.coverMissingText}>Немає обкладинки</Text>
      </View>
    );
  }
  return (
    <Image
      source={{ uri: src }}
      style={styles.coverImg}
      resizeMode="contain"
      onError={() => setFailed(true)}
    />
  );
}

function ShelfPhotoThumb({ uri }: { uri: string }) {
  const src = useResolvedMediaUrl(uri);
  if (!src) return null;
  return <Image source={{ uri: src }} style={styles.shelfPhotoThumb} />;
}

export default function ShelfScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { width: winW, height: winH } = useWindowDimensions();
  const gridCols = winW >= 992 ? 5 : 2;
  const gridGap = 8;
  const gridPad = 8;
  const cardWidth =
    (winW - gridPad * 2 - gridGap * (gridCols - 1)) / gridCols;
  const [shelves, setShelves] = useState<Shelf[]>([]);
  const [pending, setPending] = useState<Shelf[]>([]);
  const [lentOutCount, setLentOutCount] = useState(0);
  const [priceTotal, setPriceTotal] = useState("0.00");
  const [sharedNote, setSharedNote] = useState<string | null>(null);
  const [iAmLibraryAdmin, setIAmLibraryAdmin] = useState(true);
  const [isSharedLibrary, setIsSharedLibrary] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
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
  const [searchMsg, setSearchMsg] = useState("");
  const searchTickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const ISBN_SEARCH_LABELS = ["ISBNdb", "Open Library", "Google Books", "LibraryThing"];
  const [ageShelf, setAgeShelf] = useState<Shelf | null>(null);
  const [ageMin, setAgeMin] = useState("0");
  const [ageMax, setAgeMax] = useState("18");
  const [listingShelf, setListingShelf] = useState<Shelf | null>(null);
  const [listingBulk, setListingBulk] = useState(false);
  const [detailShelf, setDetailShelf] = useState<Shelf | null>(null);
  const [isbnInfoOpen, setIsbnInfoOpen] = useState(false);
  const [listingFlags, setListingFlags] = useState({
    is_fee_sharing: true,
    is_hidden: false,
    is_for_rent: false,
    is_for_exchange: false,
    is_free_of_deposit: false,
  });
  const [saleGift, setSaleGift] = useState<SaleGift>("");
  const [salePrice, setSalePrice] = useState("");
  const [rentPrice, setRentPrice] = useState("");
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
    const nextShelves = Array.isArray(data?.shelves) ? data.shelves : [];
    setShelves(nextShelves);
    setDetailShelf((prev) =>
      prev ? nextShelves.find((s) => s.id === prev.id) ?? prev : null
    );
    setPending(Array.isArray(data?.pending_returns) ? data.pending_returns : []);
    setLentOutCount(Number(data?.lent_out_count) || 0);
    setPriceTotal(data?.price_total_uah || "0.00");
    setIsSharedLibrary(!!data?.is_shared_library);
    setIAmLibraryAdmin(
      !data?.is_shared_library || !!data?.i_am_library_admin
    );
    if (data?.is_shared_library) {
      setSharedNote(
        `Спільна бібліотека «${data.shared_library_name || ""}» (${data.shared_member_count || 0} учасн.) — усі спільні примірники видно кожному.`
      );
    } else {
      setSharedNote(null);
    }
    setSelectedIds((prev) =>
      prev.filter((id) => (data?.shelves || []).some((s) => s.id === id && !s.borrowed_from))
    );
  };

  const refreshPrice = async (bookId: number) => {
    try {
      const r = await ShelfApi.refreshPrice(bookId);
      setShelves((prev) =>
        prev.map((s) =>
          s.book.id === bookId ? { ...s, price_eval: r.price_eval as BookPriceEval } : s
        )
      );
      setDetailShelf((prev) =>
        prev && prev.book.id === bookId
          ? { ...prev, price_eval: r.price_eval as BookPriceEval }
          : prev
      );
      Alert.alert("Ціна", "Оновлення оцінки запущено. Оновіть полицю за хвилину.");
      setTimeout(() => {
        load().catch(() => undefined);
      }, 2500);
    } catch (e) {
      Alert.alert("Ціна", e instanceof ApiError ? e.message : String(e));
    }
  };

  const refreshMetadata = async (bookId: number) => {
    try {
      const r = await ShelfApi.refreshMetadata(bookId);
      if (r.book) {
        setShelves((prev) =>
          prev.map((s) => (s.book.id === bookId ? { ...s, book: { ...s.book, ...r.book } } : s))
        );
      }
      Alert.alert(
        "Каталог",
        r.detail || (r.search_source ? `Оновлено з ${r.search_source}` : "Метадані оновлено.")
      );
      await load();
    } catch (e) {
      const payload =
        e instanceof ApiError
          ? (e.payload as { search_log?: { label?: string; status?: string; detail?: string }[] })
          : null;
      const log = formatSearchLog(payload?.search_log);
      Alert.alert(
        "Каталог",
        [e instanceof ApiError ? e.message : String(e), log].filter(Boolean).join("\n\n")
      );
    }
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) => Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e)));
    }, [])
  );

  const stopSearchTick = () => {
    if (searchTickRef.current) {
      clearInterval(searchTickRef.current);
      searchTickRef.current = null;
    }
  };

  const startSearchTick = () => {
    stopSearchTick();
    let i = 0;
    setSearchMsg(`Шукаємо в ${ISBN_SEARCH_LABELS[0]}…`);
    searchTickRef.current = setInterval(() => {
      i = (i + 1) % ISBN_SEARCH_LABELS.length;
      setSearchMsg(`Шукаємо в ${ISBN_SEARCH_LABELS[i]}…`);
    }, 1200);
  };

  const formatSearchLog = (
    log?: { label?: string; status?: string; detail?: string }[]
  ) => {
    if (!log?.length) return "";
    return log
      .filter((s) => s && s.label && s.status !== "searching")
      .map((s) => {
        const mark = s.status === "hit" ? "✓" : "·";
        return `${mark} ${s.label}${s.detail ? ` — ${s.detail}` : ""}`;
      })
      .join("\n");
  };

  const addIsbn = useCallback(async (raw?: string, confirmExtra = false) => {
    const code = (raw ?? isbn).trim();
    const norm = normalizeIsbn(code);
    if (!norm) {
      if (code) Alert.alert("ISBN", "Потрібен повний ISBN (10 або 13 символів).");
      return;
    }
    if (adding) return;
    if (!confirmExtra && norm === lastAutoRef.current) return;
    lastAutoRef.current = norm;
    setAdding(true);
    startSearchTick();
    try {
      const res = await ShelfApi.addIsbn(norm, confirmExtra);
      stopSearchTick();
      const logText = formatSearchLog(
        res && typeof res === "object" && "search_log" in res
          ? (res as { search_log?: { label?: string; status?: string; detail?: string }[] })
              .search_log
          : undefined
      );
      if (res && typeof res === "object" && "needs_confirmation" in res && res.needs_confirmation) {
        lastAutoRef.current = "";
        setSearchMsg("");
        Alert.alert(
          "Примірник уже є",
          [String(res.detail || `Уже є ${res.existing_count} шт. Додати ще один?`), logText]
            .filter(Boolean)
            .join("\n\n"),
          [
            { text: "Ні", style: "cancel" },
            {
              text: "Так, додати",
              onPress: () => {
                void addIsbn(norm, true);
              },
            },
          ]
        );
        return;
      }
      if (res && typeof res === "object" && "pending_approval" in res && res.pending_approval) {
        const partnerId = (res as { chat_partner_id?: number }).chat_partner_id;
        setSearchMsg("");
        Alert.alert(
          "Спільна бібліотека",
          [
            String(res.detail || "ISBN уже є. Запит надіслано адміністратору в чат."),
            logText,
          ]
            .filter(Boolean)
            .join("\n\n"),
          partnerId
            ? [
                { text: "OK" },
                {
                  text: "Відкрити чат",
                  onPress: () => router.push(`/chat/${partnerId}`),
                },
              ]
            : [{ text: "OK" }]
        );
        setIsbn("");
        lastAutoRef.current = "";
        return;
      }
      const src =
        res && typeof res === "object" && "search_source" in res
          ? String((res as { search_source?: string }).search_source || "")
          : "";
      setSearchMsg(src ? `Знайдено в ${src}` : "Додано");
      setIsbn("");
      lastAutoRef.current = "";
      await load();
      setTimeout(() => setSearchMsg(""), 4000);
    } catch (e) {
      stopSearchTick();
      lastAutoRef.current = "";
      const payload =
        e instanceof ApiError
          ? (e.payload as {
              needs_confirmation?: boolean;
              detail?: string;
              existing_count?: number;
              search_log?: { label?: string; status?: string; detail?: string }[];
            })
          : null;
      const logText = formatSearchLog(payload?.search_log);
      if (e instanceof ApiError && e.status === 409) {
        if (payload?.needs_confirmation) {
          setSearchMsg("");
          Alert.alert(
            "Примірник уже є",
            [String(payload.detail || `Уже є ${payload.existing_count} шт. Додати ще один?`), logText]
              .filter(Boolean)
              .join("\n\n"),
            [
              { text: "Ні", style: "cancel" },
              {
                text: "Так, додати",
                onPress: () => {
                  void addIsbn(norm, true);
                },
              },
            ]
          );
          return;
        }
      }
      setSearchMsg("");
      Alert.alert(
        "ISBN",
        [e instanceof ApiError ? e.message : String(e), logText].filter(Boolean).join("\n\n")
      );
    } finally {
      stopSearchTick();
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
      stopSearchTick();
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

  const saveAge = async (mn: number, mx: number) => {
    if (!ageShelf) return;
    try {
      await ShelfApi.readerAge(ageShelf.id, mn, mx);
      await load();
    } catch (e) {
      Alert.alert("Вік", e instanceof ApiError ? e.message : String(e));
    }
  };

  const ageSavedKeyRef = useRef("");
  useEffect(() => {
    if (!ageShelf) return;
    const mn = Number(ageMin);
    const mx = Number(ageMax);
    if (Number.isNaN(mn) || Number.isNaN(mx)) return;
    const key = `${ageShelf.id}:${mn}:${mx}`;
    if (key === ageSavedKeyRef.current) return;
    const t = setTimeout(() => {
      ageSavedKeyRef.current = key;
      saveAge(mn, mx).catch(() => {
        ageSavedKeyRef.current = "";
      });
    }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ageMin, ageMax, ageShelf?.id]);

  const openListing = (s?: Shelf) => {
    const target = s || shelves.find((x) => selectedIds.includes(x.id));
    if (target) {
      setListingFlags({
        is_fee_sharing: !!target.is_fee_sharing,
        is_hidden: !!target.is_hidden,
        is_for_rent: !!target.is_for_rent,
        is_for_exchange: !!target.is_for_exchange,
        is_free_of_deposit: !!target.is_free_of_deposit,
      });
      setSaleGift(
        (target.sale_gift as SaleGift) ||
          (target.is_for_sale ? "for_sale" : target.is_as_gift ? "as_gift" : "")
      );
      setSalePrice(target.sale_price || "");
      setRentPrice(target.rent_price_per_day || "");
    } else {
      setListingFlags({
        is_fee_sharing: true,
        is_hidden: false,
        is_for_rent: false,
        is_for_exchange: false,
        is_free_of_deposit: false,
      });
      setSaleGift("");
      setSalePrice("");
      setRentPrice("");
    }
    setListingBulk(!s && selectedIds.length > 0);
    setListingShelf(s || target || ({ id: 0 } as Shelf));
  };

  const handlePendingChat = (res: unknown, title: string) => {
    if (res && typeof res === "object" && "pending_approval" in res && (res as { pending_approval?: boolean }).pending_approval) {
      const partner = (res as { chat_partner_id?: number }).chat_partner_id;
      Alert.alert(
        title,
        (res as { detail?: string }).detail ||
          "Запит надіслано адміністратору спільної бібліотеки в чат.",
        partner
          ? [
              { text: "OK" },
              { text: "Відкрити чат", onPress: () => router.push(`/chat/${partner}`) },
            ]
          : [{ text: "OK" }]
      );
      return true;
    }
    return false;
  };

  const saveListing = async () => {
    if (!listingShelf) return;
    const body = {
      ...listingFlags,
      sale_gift: saleGift,
      sale_price: saleGift === "for_sale" ? salePrice || null : null,
      rent_price_per_day: listingFlags.is_for_rent ? rentPrice || null : null,
    };
    try {
      if (listingBulk && selectedIds.length) {
        const res = await ShelfApi.bulk({
          action: "listing",
          shelf_ids: selectedIds,
          ...body,
        });
        setListingShelf(null);
        setListingBulk(false);
        setSelectedIds([]);
        if (handlePendingChat(res, "Статуси")) {
          await load();
          return;
        }
      } else if (listingShelf.id) {
        const res = await ShelfApi.updateListing(listingShelf.id, body);
        setListingShelf(null);
        if (handlePendingChat(res, "Статуси")) {
          await load();
          return;
        }
      }
      setListingShelf(null);
      setListingBulk(false);
      await load();
    } catch (e) {
      Alert.alert("Статус", e instanceof ApiError ? e.message : String(e));
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const bulkDelete = () => {
    if (!selectedIds.length) return;
    Alert.alert(
      "Видалити",
      `Прибрати ${selectedIds.length} примірник(ів) з полиці?` +
        (isSharedLibrary && !iAmLibraryAdmin
          ? "\nЗапит піде адміністратору в чат."
          : ""),
      [
        { text: "Скасувати", style: "cancel" },
        {
          text: "Видалити",
          style: "destructive",
          onPress: async () => {
            try {
              const res = await ShelfApi.bulk({
                action: "delete",
                shelf_ids: selectedIds,
              });
              setSelectedIds([]);
              if (handlePendingChat(res, "Видалення")) {
                await load();
                return;
              }
              await load();
            } catch (e) {
              Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e));
            }
          },
        },
      ]
    );
  };

  const act = async (s: Shelf) => {
    try {
      if (s.borrowed_from) {
        await ShelfApi.returnBook(s.id);
        await load();
        return;
      }
      const res = await ShelfApi.remove(s.id);
      if (handlePendingChat(res, "Видалення")) {
        await load();
        return;
      }
      await load();
    } catch (e) {
      Alert.alert("Полиця", e instanceof ApiError ? e.message : String(e));
    }
  };

  const confirm = async (s: Shelf) => {
    try {
      if (s.requires_qr_scan) {
        router.push(`/qr-scan?return_shelf_id=${s.id}`);
        return;
      }
      await ShelfApi.confirmReturn(s.id);
      Alert.alert("Повернення", "Підтверджено.");
      setDetailShelf(null);
      await load();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      if (/Відскануйте QR|QR-наклейк/i.test(msg)) {
        router.push(`/qr-scan?return_shelf_id=${s.id}`);
        return;
      }
      Alert.alert("Повернення", msg);
    }
  };

  const confirmPendingForOwner = (ownerShelf: Shelf) => {
    const pid = ownerShelf.pending_return_shelf_id;
    if (!pid) return;
    const borrowerRow = pending.find((p) => p.id === pid);
    confirm(
      borrowerRow ?? {
        ...ownerShelf,
        id: pid,
        requires_qr_scan: ownerShelf.requires_qr_scan,
      }
    );
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.screen }}>
      <View style={styles.toolbar}>
        <CyrillicTextInput
          placeholder={adding ? "Шукаємо в каталогах…" : "ISBN 10/13 — додається сам"}
          placeholderTextColor={colors.muted}
          style={styles.isbnInput}
          value={isbn}
          onChangeText={onIsbnChange}
          autoCapitalize="none"
          keyboardType="number-pad"
          maxLength={13}
          editable={!adding}
        />
        <ShelfLogoChip
          title="Вручну"
          icon="edit"
          style={styles.manualChip}
          accessibilityLabel="Додати книгу вручну"
          onPress={() => {
            resetManualForm();
            setManualOpen(true);
          }}
        />
      </View>
      {searchMsg ? <Text style={styles.searchMsg}>{searchMsg}</Text> : null}
      <FlatList
        key={`shelf-grid-${gridCols}`}
        data={shelves}
        keyExtractor={(s) => String(s.id)}
        numColumns={gridCols}
        columnWrapperStyle={styles.flexRow}
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
            {sharedNote ? <Text style={styles.sharedHint}>{sharedNote}</Text> : null}
            <Text style={styles.selectHint}>
              Обкладинка · назва · автор · вибір. Натисніть обкладинку для деталей.
              {isSharedLibrary && iAmLibraryAdmin
                ? " Адмін може видаляти будь-які примірники без підтвердження; власники отримають лише повідомлення в чаті."
                : isSharedLibrary && !iAmLibraryAdmin
                  ? " У спільній бібліотеці зміни підуть адміну в чат."
                  : ""}
            </Text>
            {selectedIds.length > 0 ? (
              <View style={styles.selectionBar}>
                <Text style={styles.selectionCount}>Вибрано: {selectedIds.length}</Text>
                <View style={styles.selectionActions}>
                  <ShelfLogoChip
                    title="Статуси"
                    icon="tags"
                    onPress={() => openListing()}
                  />
                  <ShelfLogoChip
                    title="Видалити"
                    icon="trash"
                    danger
                    onPress={bulkDelete}
                  />
                  <ShelfLogoChip
                    title="Скасувати"
                    icon="close"
                    onPress={() => setSelectedIds([])}
                  />
                </View>
              </View>
            ) : null}
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
                  <View key={s.id} style={[styles.card, styles.pendingCard, styles.pendingCardRow]}>
                    <View style={styles.pendingThumbWrap}>
                      <ShelfCoverImage uri={bookCoverFromDb(s.book)} />
                    </View>
                    <View style={[styles.cardBody, styles.pendingCardBody]}>
                      <Text style={styles.title}>{s.book.title}</Text>
                      <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center" }}>
                        <Text style={styles.meta}>від </Text>
                        <UserNameLink user={s.user} style={styles.meta} />
                      </View>
                      <ShelfLogoChip
                        title="Підтвердити повернення"
                        icon="check"
                        style={{ marginTop: 10 }}
                        onPress={() => confirm(s)}
                      />
                    </View>
                  </View>
                ))}
              </View>
            ) : null}
          </View>
        }
        contentContainerStyle={{ paddingBottom: 24, paddingHorizontal: gridPad }}
        ListEmptyComponent={
          <Text style={styles.empty}>На полиці ще немає примірників. Додайте ISBN вище.</Text>
        }
        renderItem={({ item }) => {
          const coverUri = bookCoverFromDb(item.book);
          const selectable = !item.borrowed_from;
          const selected = selectedIds.includes(item.id);
          return (
            <View
              style={[
                styles.flexCard,
                { width: cardWidth, maxWidth: cardWidth },
                selected && styles.cardSelected,
              ]}
            >
              <View style={styles.coverWrap}>
                <Pressable
                  onPress={() => setDetailShelf(item)}
                  accessibilityRole="button"
                  accessibilityLabel={`Відкрити профіль: ${item.book.title}`}
                  style={styles.coverPress}
                >
                  <ShelfCoverImage uri={coverUri} />
                </Pressable>
                {selectable ? (
                  <Pressable
                    onPress={() => toggleSelect(item.id)}
                    style={[styles.selectCheck, selected && styles.selectCheckOn]}
                    hitSlop={6}
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: selected }}
                    accessibilityLabel={`Вибрати ${item.book.title}`}
                  >
                    {selected ? <View style={styles.selectCheckMark} /> : null}
                  </Pressable>
                ) : null}
              </View>
              <Pressable
                onPress={() => setDetailShelf(item)}
                accessibilityRole="button"
                style={styles.flexCardMeta}
              >
                <Text style={styles.flexTitle} numberOfLines={2}>
                  {item.book.title}
                </Text>
                <Text style={styles.flexAuthor} numberOfLines={2}>
                  {item.book.authors || "Автор невідомий"}
                </Text>
              </Pressable>
            </View>
          );
        }}
      />

      <ShelfInstanceDetailModal
        visible={!!detailShelf}
        book={detailShelf?.book ?? null}
        onClose={() => setDetailShelf(null)}
        onCoverPress={() => setIsbnInfoOpen(true)}
        photoStrip={
          detailShelf && (detailShelf.book.photo_urls || []).length > 0 ? (
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.shelfPhotoStrip}
            >
              {(detailShelf.book.photo_urls || []).map((u, i) => (
                <ShelfPhotoThumb key={`${u}-${i}`} uri={u} />
              ))}
            </ScrollView>
          ) : null
        }
        titleLine={
          detailShelf ? (
            <Text style={styles.meta}>
              {detailShelf.book.authors || "Автор невідомий"}
              {"\n"}
              {detailShelf.copy_id ? `Примірник #${detailShelf.copy_id} · ` : ""}
              {detailShelf.book.isbn?.startsWith("9799") || detailShelf.book.isbn_missing
                ? detailShelf.book.note || "ISBN code not exists"
                : detailShelf.book.isbn
                  ? `ISBN-13 ${detailShelf.book.isbn}${
                      detailShelf.book.isbn10 ? ` · ISBN-10 ${detailShelf.book.isbn10}` : ""
                    }`
                  : ""}
              {` · ${detailShelf.book.reader_age_summary}`}
            </Text>
          ) : null
        }
        footer={
          detailShelf ? (
            <ScrollView
              style={styles.detailFooterScroll}
              contentContainerStyle={styles.detailFooterContent}
              showsVerticalScrollIndicator={false}
              keyboardShouldPersistTaps="handled"
              nestedScrollEnabled
            >
              {detailShelf.pending_return_shelf_id && !detailShelf.borrowed_from ? (
                <ShelfDetailActionBtn
                  primary
                  icon={detailShelf.requires_qr_scan ? "qr" : "check"}
                  title={
                    detailShelf.requires_qr_scan
                      ? "Скан QR → повернуто"
                      : "Підтвердити повернення"
                  }
                  subtitle={(() => {
                    const row = pending.find(
                      (p) => p.id === detailShelf.pending_return_shelf_id
                    );
                    return row?.user
                      ? `${row.user.username} повідомив про повернення`
                      : "Позичальник повідомив про повернення";
                  })()}
                  onPress={() => confirmPendingForOwner(detailShelf)}
                />
              ) : null}
              {detailShelf.borrowed_from && !detailShelf.return_pending ? (
                <ShelfDetailActionBtn
                  primary
                  icon="return"
                  title="Повернути власнику"
                  subtitle="Повідомити про повернення книги"
                  onPress={async () => {
                    await act(detailShelf);
                    setDetailShelf(null);
                  }}
                />
              ) : null}
              <ShelfDetailActionBtn
                icon="add"
                title="Написати пост"
                subtitle="Відгук про цю книгу"
                onPress={() =>
                  router.push({
                    pathname: "/post/new",
                    params: {
                      mode: "feedback",
                      book_id: String(detailShelf.book.id),
                    },
                  })
                }
              />
              <ShelfDetailActionBtn
                icon="library"
                title="Усі примірники ISBN"
                subtitle="Інші копії з цим ISBN"
                onPress={() => {
                  setDetailShelf(null);
                  router.push(`/book/${detailShelf.book.id}`);
                }}
              />
              <ShelfDetailActionBtn
                icon="barcode"
                title="Дані ISBN"
                subtitle="Повна картка з каталогу"
                onPress={() => setIsbnInfoOpen(true)}
              />
              {detailShelf.copy_id ? (
                <ShelfDetailActionBtn
                  icon="history"
                  title="Історія подій"
                  subtitle="Хто тримав цей примірник"
                  onPress={() => {
                    const cid = detailShelf.copy_id!;
                    setDetailShelf(null);
                    router.push(`/copy/${cid}`);
                  }}
                />
              ) : null}
              {!detailShelf.borrowed_from && detailShelf.copy_id ? (
                <ShelfDetailActionBtn
                  icon="qr"
                  title="Скан QR"
                  subtitle="Прив’язати або перевірити наклейку"
                  onPress={() => {
                    const cid = detailShelf.copy_id!;
                    setDetailShelf(null);
                    router.push(`/qr-scan?attach_copy_id=${cid}`);
                  }}
                />
              ) : null}
              {detailShelf.borrowed_from ? (
                <ShelfDetailActionBtn
                  icon="chat"
                  title="Чат з власником"
                  subtitle={detailShelf.borrowed_from.username}
                  onPress={() => router.push(`/chat/${detailShelf.borrowed_from!.id}`)}
                />
              ) : null}
              {!detailShelf.borrowed_from ? (
                <ShelfDetailActionBtn
                  icon="tags"
                  title="Статуси"
                  subtitle="Продаж, оренда, обмін, видимість"
                  onPress={() => {
                    const s = detailShelf;
                    setDetailShelf(null);
                    openListing(s);
                  }}
                />
              ) : null}
              {!detailShelf.borrowed_from && detailShelf.can_edit_manual ? (
                <ShelfDetailActionBtn
                  icon="edit"
                  title="Редагувати"
                  subtitle="Назва, автори, фото вручну"
                  onPress={() => {
                    setDetailShelf(null);
                    openEditManual(detailShelf);
                  }}
                />
              ) : null}
              {!detailShelf.borrowed_from ? (
                <ShelfDetailActionBtn
                  icon="people"
                  title="Вік читача"
                  subtitle="Рекомендований діапазон віку"
                  onPress={() => {
                    const mn = String(detailShelf.book.min_readers_age);
                    const mx = String(detailShelf.book.max_readers_age);
                    ageSavedKeyRef.current = `${detailShelf.id}:${mn}:${mx}`;
                    setAgeMin(mn);
                    setAgeMax(mx);
                    setAgeShelf(detailShelf);
                  }}
                />
              ) : null}
              {!detailShelf.borrowed_from &&
              detailShelf.book.isbn &&
              !detailShelf.book.isbn.startsWith("9799") &&
              !detailShelf.book.isbn_missing ? (
                <ShelfDetailActionBtn
                  icon="cloud"
                  title="Оновити з каталогу"
                  subtitle="Метадані з ISBNdb / Open Library"
                  onPress={() => refreshMetadata(detailShelf.book.id)}
                />
              ) : null}
              <ShelfDetailActionBtn
                icon="cash"
                title={
                  detailShelf.price_eval?.status === "ready"
                    ? "Оновити оцінку ціни"
                    : detailShelf.price_eval
                      ? "Оновити ціну"
                      : "Оцінити ціну"
                }
                subtitle={
                  detailShelf.price_eval?.status === "ready" && detailShelf.price_eval.price_avg
                    ? `Зараз ≈ ${detailShelf.price_eval.price_avg} ₴`
                    : "Ринкова оцінка ISBN"
                }
                onPress={() => refreshPrice(detailShelf.book.id)}
              />
              {detailShelf.price_eval?.status === "ready" &&
              (detailShelf.price_eval.quotes || []).length > 0 ? (
                <ShelfDetailActionBtn
                  icon="list"
                  title={`Price sources (${detailShelf.price_eval.source_count})`}
                  subtitle="Джерела ринкової оцінки"
                  onPress={() => setSourcesOpen(detailShelf.price_eval?.quotes || [])}
                />
              ) : null}
              {!detailShelf.borrowed_from ? (
                <ShelfDetailActionBtn
                  danger
                  icon="trash"
                  title="Видалити з полиці"
                  subtitle="Прибрати цей примірник"
                  onPress={() => {
                    const s = detailShelf;
                    Alert.alert(
                      "Видалити",
                      `Прибрати «${s.book.title}» з полиці?` +
                        (isSharedLibrary && !iAmLibraryAdmin
                          ? "\nЗапит піде адміністратору в чат."
                          : isSharedLibrary && iAmLibraryAdmin
                            ? "\nВласники отримають лише повідомлення в чаті."
                            : ""),
                      [
                        { text: "Скасувати", style: "cancel" },
                        {
                          text: "Видалити",
                          style: "destructive",
                          onPress: async () => {
                            setDetailShelf(null);
                            await act(s);
                          },
                        },
                      ]
                    );
                  }}
                />
              ) : null}
            </ScrollView>
          ) : null
        }
      >
        {detailShelf ? (
          <>
            {detailShelf.pending_return_shelf_id && !detailShelf.borrowed_from ? (
              <View style={styles.pendingInline}>
                {(() => {
                  const row = pending.find((p) => p.id === detailShelf.pending_return_shelf_id);
                  return row?.user ? (
                    <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center" }}>
                      <UserNameLink user={row.user} style={[styles.meta, { color: colors.stampOk }]} />
                      <Text style={[styles.meta, { color: colors.stampOk, fontWeight: "600" }]}>
                        {" "}
                        повідомив про повернення.
                      </Text>
                    </View>
                  ) : (
                    <Text style={[styles.meta, { color: colors.stampOk, fontWeight: "600" }]}>
                      Позичальник повідомив про повернення.
                    </Text>
                  );
                })()}
              </View>
            ) : null}
            {detailShelf.borrowed_from ? (
              <View style={{ flexDirection: "row", flexWrap: "wrap", marginTop: 6 }}>
                <Text style={styles.meta}>Позичено у </Text>
                <UserNameLink user={detailShelf.borrowed_from} style={styles.meta} />
                <Text
                  style={[
                    styles.meta,
                    detailShelf.is_overdue ? { color: colors.stamp, fontWeight: "700" } : null,
                  ]}
                >
                  {detailShelf.due_date ? ` · до ${detailShelf.due_date}` : ""}
                  {detailShelf.is_overdue
                    ? " · прострочено"
                    : detailShelf.days_left != null
                      ? ` · ще ${detailShelf.days_left} дн.`
                      : ""}
                  {detailShelf.return_pending ? " · очікує підтвердження" : ""}
                </Text>
              </View>
            ) : null}
            {!!detailShelf.listing_status_display && !detailShelf.borrowed_from ? (
              <Text style={styles.meta}>
                {detailShelf.listing_status_display}
                {detailShelf.is_for_sale && detailShelf.sale_price
                  ? ` · ${detailShelf.sale_price} ₴`
                  : ""}
                {detailShelf.is_for_rent && detailShelf.rent_price_per_day
                  ? ` · ${detailShelf.rent_price_per_day} ₴/день`
                  : ""}
              </Text>
            ) : null}
            {detailShelf.owners_label && !detailShelf.borrowed_from ? (
              <Text style={styles.meta}>Власники: {detailShelf.owners_label}</Text>
            ) : null}
            {detailShelf.price_eval?.status === "ready" && detailShelf.price_eval.price_avg ? (
              <View style={styles.priceRow}>
                <Text style={styles.priceAvg}>
                  ≈ {detailShelf.price_eval.price_avg} ₴
                  <Text style={styles.meta}>
                    {" "}
                    ({detailShelf.price_eval.price_min}–{detailShelf.price_eval.price_max})
                  </Text>
                </Text>
              </View>
            ) : (
              <View style={styles.priceRow}>
                <Text style={styles.meta}>
                  {detailShelf.price_eval?.status === "pending"
                    ? "Оцінка ціни…"
                    : detailShelf.price_eval?.status === "missing"
                      ? "Ціну не знайдено"
                      : "Ціна ще не оцінена"}
                </Text>
              </View>
            )}
          </>
        ) : null}
      </ShelfInstanceDetailModal>

      <BookIsbnInfoModal
        book={detailShelf?.book ?? null}
        visible={isbnInfoOpen && !!detailShelf}
        onClose={() => setIsbnInfoOpen(false)}
        footer={
          detailShelf ? (
            <Pressable
              style={styles.isbnModalFooterBtn}
              onPress={() => {
                const bid = detailShelf.book.id;
                setIsbnInfoOpen(false);
                setDetailShelf(null);
                router.push(`/book/${bid}`);
              }}
            >
              <Text style={styles.isbnModalFooterText}>Усі примірники ISBN</Text>
            </Pressable>
          ) : null
        }
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
            <ShelfLogoChip
              title={aiBusy ? "AI…" : "AI розпізнати"}
              icon="cloud"
              disabled={aiBusy || manualPhotos.length === 0}
              onPress={() => {
                void recognizeFromPhotos();
              }}
            />
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
          <ShelfLogoChip
            title={editShelfId ? "Оновити" : "Зберегти"}
            icon="check"
            style={{ marginTop: 8 }}
            onPress={addManual}
          />
          <ShelfLogoChip
            title="Очистити всі поля"
            icon="trash"
            danger
            style={{ marginTop: 8 }}
            onPress={() => {
              const keepEdit = editShelfId;
              resetManualForm();
              if (keepEdit) setEditShelfId(keepEdit);
              setAiStatus("");
            }}
          />
          <ShelfLogoChip
            title="Закрити"
            icon="close"
            style={{ marginTop: 8 }}
            onPress={() => {
              setManualOpen(false);
              resetManualForm();
            }}
          />
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
            <Text style={styles.meta}>0–18 (18 = 18+) · зберігається автоматично</Text>
            <ShelfLogoChip
              title="Закрити"
              icon="close"
              style={{ marginTop: 12 }}
              onPress={() => setAgeShelf(null)}
            />
          </View>
        </View>
      </Modal>

      <Modal
        visible={!!listingShelf}
        transparent
        animationType="fade"
        onRequestClose={() => setListingShelf(null)}
      >
        <View style={styles.backdrop}>
          <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center", padding: 20 }}>
            <View style={styles.sheet}>
              <Text style={styles.modalH}>
                {listingBulk
                  ? `Статуси (${selectedIds.length})`
                  : "Статуси примірника"}
              </Text>
              <Text style={styles.meta}>
                {listingBulk
                  ? isSharedLibrary && !iAmLibraryAdmin
                    ? "Запит піде адміністратору в чат"
                    : "Застосується до вибраних"
                  : listingShelf?.book?.title || ""}
              </Text>
              {LISTING_CHECKBOX_OPTIONS.map((opt) => {
                const key = opt.key as keyof typeof listingFlags;
                const on = !!listingFlags[key];
                return (
                  <ShelfCheckRow
                    key={opt.key}
                    label={opt.label}
                    checked={on}
                    onPress={() =>
                      setListingFlags((prev) => ({ ...prev, [key]: !prev[key] }))
                    }
                  />
                );
              })}
              <Text style={[styles.meta, { marginTop: 12, fontWeight: "700" }]}>
                Продаж / подарунок (взаємовиключно)
              </Text>
              {SALE_GIFT_OPTIONS.map((opt) => (
                <ShelfRadioRow
                  key={opt.value || "neither"}
                  label={opt.label}
                  selected={saleGift === opt.value}
                  onPress={() => setSaleGift(opt.value)}
                />
              ))}
              {saleGift === "for_sale" && (
                <TextInput
                  style={[styles.age, { width: "100%", marginTop: 12 }]}
                  keyboardType="decimal-pad"
                  placeholder="Ціна продажу ₴"
                  value={salePrice}
                  onChangeText={setSalePrice}
                />
              )}
              {listingFlags.is_for_rent && (
                <TextInput
                  style={[styles.age, { width: "100%", marginTop: 12 }]}
                  keyboardType="decimal-pad"
                  placeholder="Оренда ₴/день"
                  value={rentPrice}
                  onChangeText={setRentPrice}
                />
              )}
              <Text style={[styles.meta, { marginTop: 10 }]}>
                {saleGift === "for_sale" ||
                saleGift === "as_gift" ||
                listingFlags.is_free_of_deposit
                  ? "Депозит не потрібен"
                  : "Позика потребує депозит до повернення"}
              </Text>
              <View style={styles.listingActions}>
                <ShelfLogoChip
                  title="Зберегти"
                  icon="check"
                  style={styles.listingActionChip}
                  onPress={saveListing}
                />
                <ShelfLogoChip
                  title="Скасувати"
                  icon="close"
                  style={styles.listingActionChip}
                  onPress={() => setListingShelf(null)}
                />
              </View>
            </View>
          </ScrollView>
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
            <ShelfLogoChip
              title="Закрити"
              icon="close"
              style={{ marginTop: 12 }}
              onPress={() => setSourcesOpen(null)}
            />
          </View>
        </View>
      </Modal>

      {/* Scan FAB — same chrome as Create Post, classic camera instead of + */}
      <Pressable
        style={({ pressed }) => [
          styles.scanFab,
          { bottom: Math.max(16, insets.bottom + 12), right: 16 },
          pressed && styles.scanFabPressed,
        ]}
        onPress={() => setScanOpen(true)}
        accessibilityRole="button"
        accessibilityLabel="Сканувати ISBN камерою"
      >
        <ImageBackground
          source={require("../../assets/fab-gradient.png")}
          style={styles.scanFabBg}
          imageStyle={styles.scanFabBgImg}
        >
          <CameraGlyph color={colors.white} size={s(30)} />
        </ImageBackground>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", padding: 12, gap: 8 },
  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    gap: 10,
  },
  manualChip: {
    marginLeft: "auto",
  },
  scanFab: {
    position: "absolute",
    width: s(64),
    height: s(64),
    borderRadius: s(32),
    zIndex: 40,
    elevation: 12,
    shadowColor: "#E83E8C",
    shadowOpacity: 0.5,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 5 },
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.55)",
    overflow: "hidden",
    backgroundColor: "#E83E8C",
  },
  scanFabBg: {
    flex: 1,
    width: "100%",
    height: "100%",
    alignItems: "center",
    justifyContent: "center",
  },
  scanFabBgImg: {
    borderRadius: s(32),
  },
  scanFabPressed: {
    opacity: 0.92,
    transform: [{ scale: 0.96 }],
  },
  empty: { color: colors.muted, textAlign: "center", marginTop: 40, paddingHorizontal: 24 },
  physHint: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 16,
    paddingHorizontal: 16,
    paddingTop: 4,
    paddingBottom: 4,
  },
  sharedHint: {
    color: colors.ink,
    fontSize: 12,
    lineHeight: 16,
    paddingHorizontal: 16,
    paddingBottom: 8,
    fontWeight: "600",
  },
  selectHint: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 16,
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  selectionBar: {
    marginHorizontal: 16,
    marginBottom: 10,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
    gap: 10,
  },
  selectionCount: { color: colors.ink, fontWeight: "700" },
  selectionActions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  listingActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
    marginTop: 16,
  },
  listingActionChip: {
    flexGrow: 1,
    flexBasis: "40%",
  },
  cardSelected: { borderColor: colors.stamp, borderWidth: 2 },
  flexRow: {
    gap: 8,
    marginBottom: 8,
    justifyContent: "flex-start",
  },
  flexCard: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    overflow: "hidden",
    position: "relative",
  },
  coverWrap: {
    width: "100%",
    aspectRatio: 2 / 3,
    backgroundColor: "#F3F1EC",
    position: "relative",
    overflow: "hidden",
  },
  coverPress: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 1,
  },
  coverImg: {
    width: "100%",
    height: "100%",
  },
  coverMissing: {
    flex: 1,
    width: "100%",
    height: "100%",
    alignItems: "center",
    justifyContent: "center",
    padding: 8,
  },
  coverMissingText: {
    color: colors.muted,
    fontSize: 11,
    textAlign: "center",
  },
  selectCheck: {
    position: "absolute",
    top: 8,
    right: 8,
    zIndex: 10,
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.96)",
    borderRadius: 10,
    borderWidth: 2.5,
    borderColor: "rgba(42,31,20,0.45)",
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
    elevation: 6,
  },
  selectCheckOn: {
    backgroundColor: colors.stamp,
    borderColor: colors.stamp,
  },
  selectCheckMark: {
    width: 18,
    height: 10,
    borderLeftWidth: 3.5,
    borderBottomWidth: 3.5,
    borderColor: colors.white,
    transform: [{ rotate: "-45deg" }, { translateY: -2 }],
  },
  flexCardMeta: {
    paddingHorizontal: 8,
    paddingVertical: 8,
    minHeight: 64,
  },
  flexTitle: {
    color: colors.ink,
    fontWeight: "700",
    fontSize: 13,
    lineHeight: 17,
  },
  flexAuthor: {
    color: colors.muted,
    fontSize: 11,
    marginTop: 4,
    lineHeight: 15,
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
    flex: 1,
    minWidth: 0,
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: 8,
    fontSize: 16,
    fontVariant: ["tabular-nums"],
  },
  searchMsg: {
    paddingHorizontal: 16,
    paddingBottom: 6,
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
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
  pendingCardRow: { flexDirection: "row", alignItems: "stretch" },
  pendingThumbWrap: {
    width: 72,
    height: 108,
    backgroundColor: "#F3F1EC",
    overflow: "hidden",
  },
  pendingCardBody: { flex: 1 },
  pendingInline: { marginTop: 10, marginBottom: 4 },
  detailFooterScroll: { maxHeight: "100%" },
  detailFooterContent: { paddingBottom: 4 },
  isbnModalFooterBtn: {
    marginTop: 16,
    marginBottom: 8,
    alignSelf: "stretch",
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    padding: 14,
  },
  isbnModalFooterText: { color: colors.ink, fontWeight: "700", fontSize: 16 },
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
  link: { color: colors.ink, fontWeight: "700" },
  action: { color: colors.stamp, fontWeight: "700" },
  modalH: { fontSize: 20, fontWeight: "800", color: colors.ink, marginBottom: 12 },
  btn: { backgroundColor: colors.ink, padding: 14, marginTop: 8, borderRadius: btnRadius },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.35)", justifyContent: "center", padding: 24 },
  sheet: { backgroundColor: colors.paper, padding: 20 },
  age: { flex: 1, borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, textAlign: "center", fontSize: 20, paddingVertical: 8 },
});
