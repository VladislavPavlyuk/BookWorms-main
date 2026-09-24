import { useEffect, useState } from "react";
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
import { colors } from "./theme";
import type { Shelf } from "./types";

type Props = {
  target: Shelf | null;
  myOwned: Shelf[];
  onClose: () => void;
  onDone?: () => void;
};

/** Позика / передача / обмін з вибором своєї книги. */
export function RequestModal({ target, myOwned, onClose, onDone }: Props) {
  const [offerId, setOfferId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const lent = !!(
    target &&
    (target.is_lent_out || target.lent_to || target.borrowed_from)
  );
  const targetShelfId = target?.request_shelf_id ?? target?.id ?? null;

  useEffect(() => {
    setOfferId(null);
  }, [target?.id, target?.request_shelf_id]);

  if (!target || targetShelfId == null) return null;

  const submit = async () => {
    if (lent && offerId != null) {
      Alert.alert("Запит", "Поки примірник у позиці — лише запит на передачу (без обміну).");
      return;
    }
    setBusy(true);
    try {
      const res = await ExchangeApi.create(targetShelfId, offerId);
      if (res.errors?.length) {
        Alert.alert("Запит", res.errors.join("\n"));
      } else {
        Alert.alert(
          "Запит",
          lent
            ? "Запит на передачу надіслано власнику."
            : offerId
              ? "Запит на обмін надіслано."
              : "Запит на позику надіслано."
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
              <ScrollView style={{ maxHeight: 220 }}>
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
  sheet: { backgroundColor: colors.paper, padding: 20, maxHeight: "85%" },
  h: { fontWeight: "800", color: colors.stamp, letterSpacing: 1, fontSize: 12 },
  title: { fontSize: 18, fontWeight: "800", color: colors.ink, marginTop: 6 },
  meta: { color: colors.muted, marginTop: 4, marginBottom: 8 },
  warn: { color: colors.stamp, fontWeight: "700", marginBottom: 8, lineHeight: 18 },
  sec: { fontWeight: "700", color: colors.ink, marginTop: 12, marginBottom: 6 },
  opt: { borderWidth: 1, borderColor: colors.line, padding: 10, marginBottom: 6, backgroundColor: colors.white },
  optOn: { borderColor: colors.stamp, backgroundColor: colors.paperDark },
  optText: { color: colors.ink },
  row: { flexDirection: "row", gap: 12, marginTop: 16 },
  cancel: { flex: 1, padding: 12, borderWidth: 1, borderColor: colors.line },
  cancelText: { textAlign: "center", color: colors.muted, fontWeight: "700" },
  ok: { flex: 1, padding: 12, backgroundColor: colors.ink },
  okText: { textAlign: "center", color: colors.white, fontWeight: "700" },
});
