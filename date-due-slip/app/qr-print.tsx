import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, CopyApi } from "../src/api";
import { colors, btnRadius } from "../src/theme";

type Label = {
  copy_id: number;
  title: string;
  payload: string;
  data_uri: string;
  attached: boolean;
};

/** Client preview of 2cm QR labels (print via web A4 sheet for exact size). */
export default function QrPrintScreen() {
  const router = useRouter();
  const { copy_id } = useLocalSearchParams<{ copy_id?: string }>();
  const [page, setPage] = useState<(Label | null)[]>([]);
  const [pageCount, setPageCount] = useState(0);
  const [cols, setCols] = useState(10);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      CopyApi.printLabels(
        copy_id && /^\d+$/.test(copy_id) ? { copyId: Number(copy_id) } : undefined
      )
        .then((r) => {
          setCols(r.cols);
          setPageCount(r.pages?.length ?? 0);
          setPage(r.pages?.[0] ?? []);
        })
        .catch((e) => setErr(e instanceof ApiError ? e.message : String(e)))
        .finally(() => setLoading(false));
    }, [copy_id])
  );

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.screen }} contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
      <Text style={styles.h}>Друкувати QR коди</Text>
      <Text style={styles.brand}>www.datedueslip.com</Text>
      <Text style={styles.meta}>
        Прев’ю 1-го аркуша A4: 6×6 = 36 наклейок (QR ≈ 28 мм + www.datedueslip.com). Друк — веб →
        Налаштування → Друкувати QR коди. «Скан QR» — у вікні опцій примірника.
        {pageCount > 1 ? ` Сторінок: ${pageCount}.` : ""}
      </Text>
      {loading ? <ActivityIndicator color={colors.stamp} /> : null}
      {err ? <Text style={styles.err}>{err}</Text> : null}
      <View style={[styles.grid, { width: cols * 52 }]}>
        {page.map((lab, i) => (
          <View key={lab ? lab.copy_id : `e-${i}`} style={[styles.cell, !lab && styles.cellEmpty]}>
            {lab ? (
              <>
                <Text style={styles.cellBrand}>www.datedueslip.com</Text>
                <Image source={{ uri: lab.data_uri }} style={styles.qr} />
              </>
            ) : null}
          </View>
        ))}
      </View>
      {!loading && page.length === 0 && !err ? (
        <Text style={styles.meta}>Немає примірників для друку.</Text>
      ) : null}
      <Pressable style={styles.btn} onPress={() => router.back()}>
        <Text style={styles.btnText}>← Назад</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  h: { fontWeight: "800", fontSize: 20, color: colors.ink, marginBottom: 4 },
  brand: { fontWeight: "700", color: colors.stamp, marginBottom: 8, fontSize: 13 },
  meta: { color: colors.muted, marginBottom: 16, lineHeight: 20 },
  err: { color: colors.stamp, marginBottom: 12 },
  grid: { flexDirection: "row", flexWrap: "wrap", alignSelf: "center" },
  cell: {
    width: 52,
    height: 52,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
    borderStyle: "dashed",
    padding: 4,
  },
  cellBrand: { fontSize: 7, fontWeight: "800", color: colors.ink, marginBottom: 2 },
  cellEmpty: { backgroundColor: colors.paper },
  qr: { width: 36, height: 36, backgroundColor: "#fff" },
  btn: {
    marginTop: 24,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 12,
    borderRadius: btnRadius,
    alignSelf: "flex-start",
  },
  btnText: { color: colors.ink, fontWeight: "700" },
});
