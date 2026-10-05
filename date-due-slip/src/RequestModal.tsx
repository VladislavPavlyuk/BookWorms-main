import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { ApiError, ExchangeApi } from "./api";
import { CyrillicTextInput } from "./CyrillicTextInput";
import { colors, btnRadius } from "./theme";
import type { Shelf } from "./types";

type Props = {
  target: Shelf | null;
  myOwned: Shelf[];
  /** Default loan window in days (matches server DEFAULT_LOAN_DAYS). */
  loanDays?: number;
  onClose: () => void;
  onDone?: () => void;
};

function ymd(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function addDays(base: Date, days: number): Date {
  const d = new Date(base.getTime());
  d.setDate(d.getDate() + days);
  return d;
}

/** Позика / передача / обмін з вибором своєї книги + термін повернення. */
export function RequestModal({
  target,
  myOwned,
  loanDays = 14,
  onClose,
  onDone,
}: Props) {
  const [offerId, setOfferId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const today = useMemo(() => ymd(new Date()), []);
  const defaultDue = useMemo(() => ymd(addDays(new Date(), loanDays)), [loanDays]);
  const [dueDate, setDueDate] = useState(defaultDue);

  const lent = !!(
    target &&
    (target.is_lent_out || target.lent_to || target.borrowed_from)
  );
  const targetShelfId = target?.request_shelf_id ?? target?.id ?? null;
  const isBorrow = offerId === null;

  useEffect(() => {
    setOfferId(null);
    setDueDate(defaultDue);
  }, [target?.id, target?.request_shelf_id, defaultDue]);

  if (!target || targetShelfId == null) return null;

  const submit = async () => {
    if (lent && offerId != null) {
      Alert.alert("Запит", "Поки примірник у позиці — лише запит на передачу (без обміну).");
      return;
    }
    if (isBorrow) {
      const raw = dueDate.trim();
      if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
        Alert.alert("Термін", "Вкажіть дату повернення у форматі РРРР-ММ-ДД.");
        return;
      }
      if (raw < today) {
        Alert.alert("Термін", "Дата повернення не може бути в минулому.");
        return;
      }
    }
    setBusy(true);
    try {
      const res = await ExchangeApi.create(
        targetShelfId,
        offerId,
        isBorrow ? dueDate.trim() : null
      );
      if (res.errors?.length) {
        Alert.alert("Запит", res.errors.join("\n"));
      } else {
        Alert.alert(
          "Запит",
          lent
            ? "Запит на передачу надіслано власнику."
            : offerId
              ? "Запит на обмін надіслано."
              : `Запит на позику надіслано (до ${dueDate.trim()}).`
        );
        onDone?.();
        onClose();
        setOfferId(null);
      }
    } catch (e) {
      Alert.alert("Запит", e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.h}>Запит щодо книги</Text>
          <Text style={styles.title}>{target.book.title}</Text>
          <Text style={styles.meta}>
            власник:{" "}
            {target.borrowed_from?.username || target.user.username}
          </Text>
          {lent ? (
            <Text style={styles.warn}>
              Зараз у позиці
              {target.lent_to
                ? ` у ${target.lent_to.username}`
                : target.user && target.borrowed_from
                  ? ` у ${target.user.username}`
                  : ""}
              {target.loan_due_date || target.due_date
                ? ` · до ${target.loan_due_date || target.due_date}`
                : ""}
              . Власник може схвалити передачу вам.
            </Text>
          ) : null}

          <Text style={styles.sec}>Тип</Text>
          <Pressable
            style={[styles.opt, offerId === null && styles.optOn]}
            onPress={() => setOfferId(null)}
          >
            <Text style={styles.optText}>
              {lent ? "Запит на передачу (з дозволу власника)" : "Лише позика (без обміну)"}
            </Text>
          </Pressable>

          {!lent ? (
            <>
              <Text style={styles.sec}>Або обмін — ваша книга</Text>
              <ScrollView style={{ maxHeight: 180 }}>
                {myOwned.length === 0 ? (
                  <Text style={styles.meta}>Немає власних книг для обміну</Text>
                ) : (
                  myOwned.map((s) => (
                    <Pressable
                      key={s.id}
                      style={[styles.opt, offerId === s.id && styles.optOn]}
                      onPress={() => setOfferId(s.id)}
                    >
                      <Text style={styles.optText}>{s.book.title}</Text>
                    </Pressable>
                  ))
                )}
              </ScrollView>
            </>
          ) : null}

          {isBorrow ? (
            <>
              <Text style={styles.sec}>Повернення до</Text>
              <Text style={styles.hint}>
                Запропонуйте термін (за замовчуванням {loanDays} дн.). Власник може прийняти,
                підтвердити або запропонувати іншу дату.
              </Text>
              <CyrillicTextInput
                style={styles.dateInput}
                value={dueDate}
                onChangeText={setDueDate}
                placeholder="РРРР-ММ-ДД"
                placeholderTextColor={colors.muted}
                autoCapitalize="none"
                keyboardType="numbers-and-punctuation"
                maxLength={10}
              />
              <View style={styles.quickRow}>
                {[7, 14, 30].map((d) => (
                  <Pressable
                    key={d}
                    style={styles.quick}
                    onPress={() => setDueDate(ymd(addDays(new Date(), d)))}
                  >
                    <Text style={styles.quickText}>{d} дн.</Text>
                  </Pressable>
                ))}
              </View>
            </>
          ) : null}

          <View style={styles.row}>
            <Pressable style={styles.cancel} onPress={onClose} disabled={busy}>
              <Text style={styles.cancelText}>Скасувати</Text>
            </Pressable>
            <Pressable style={styles.ok} onPress={submit} disabled={busy}>
              <Text style={styles.okText}>{busy ? "…" : "Надіслати"}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.35)", justifyContent: "flex-end" },
  sheet: { backgroundColor: colors.paper, padding: 20, maxHeight: "90%" },
  h: { fontWeight: "800", color: colors.stamp, letterSpacing: 1, fontSize: 12 },
  title: { fontSize: 18, fontWeight: "800", color: colors.ink, marginTop: 6 },
  meta: { color: colors.muted, marginTop: 4, marginBottom: 8 },
  hint: { color: colors.muted, fontSize: 12, lineHeight: 16, marginBottom: 6 },
  warn: { color: colors.stamp, fontWeight: "700", marginBottom: 8, lineHeight: 18 },
  sec: { fontWeight: "700", color: colors.ink, marginTop: 12, marginBottom: 6 },
  opt: { borderWidth: 1, borderColor: colors.line, padding: 10, marginBottom: 6, backgroundColor: colors.white },
  optOn: { borderColor: colors.stamp, backgroundColor: colors.paperDark },
  optText: { color: colors.ink },
  dateInput: {
    borderWidth: 1,
    borderColor: colors.line,
    padding: 10,
    backgroundColor: colors.white,
    color: colors.ink,
    fontSize: 16,
  },
  quickRow: { flexDirection: "row", gap: 8, marginTop: 8 },
  quick: {
    borderWidth: 1,
    borderColor: colors.line,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: btnRadius,
    backgroundColor: colors.white,
  },
  quickText: { color: colors.ink, fontWeight: "600", fontSize: 13 },
  row: { flexDirection: "row", gap: 12, marginTop: 16 },
  cancel: { flex: 1, padding: 12, borderWidth: 1, borderColor: colors.line, borderRadius: btnRadius },
  cancelText: { textAlign: "center", color: colors.muted, fontWeight: "700" },
  ok: { flex: 1, padding: 12, backgroundColor: colors.ink, borderRadius: btnRadius },
  okText: { textAlign: "center", color: colors.white, fontWeight: "700" },
});
