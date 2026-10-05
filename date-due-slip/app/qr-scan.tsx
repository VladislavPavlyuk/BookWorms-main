import { useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ApiError, CopyApi, HandoffApi } from "../src/api";
import { CopyQrScanModal } from "../src/CopyQrScanModal";
import { colors, btnRadius } from "../src/theme";

export default function QrScanScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    handoff_id?: string;
    action?: string;
    attach_copy_id?: string;
  }>();
  const [open, setOpen] = useState(true);
  const handoffId = params.handoff_id ? Number(params.handoff_id) : null;
  const action =
    params.action === "give" || params.action === "receive" ? params.action : null;
  const attachCopyId = params.attach_copy_id ? Number(params.attach_copy_id) : null;

  const onScan = async (payload: string) => {
    setOpen(false);
    try {
      if (attachCopyId) {
        await CopyApi.attachQr(attachCopyId, payload);
        Alert.alert("QR", "Наклейку прив’язано.");
        router.replace(`/copy/${attachCopyId}`);
        return;
      }
      if (handoffId && action) {
        if (action === "give") await HandoffApi.confirmGive(handoffId, payload);
        else await HandoffApi.confirmReceive(handoffId, payload);
        Alert.alert("Передача", "Підтверджено сканом QR.");
        router.back();
        return;
      }
      const res = await CopyApi.resolveQr(payload);
      if (res.copy?.id) {
        router.replace(`/copy/${res.copy.id}`);
        return;
      }
      Alert.alert("QR", "Примірник не знайдено.");
      setOpen(true);
    } catch (e) {
      Alert.alert("QR", e instanceof ApiError ? e.message : String(e));
      setOpen(true);
    }
  };

  return (
    <View style={styles.root}>
      <Text style={styles.h}>Скан QR примірника</Text>
      <Text style={styles.meta}>
        {attachCopyId
          ? `Прив’язка наклейки до #${attachCopyId}`
          : handoffId
            ? `Підтвердження передачі #${handoffId} (${action})`
            : "Ідентифікація примірника за наклейкою 2×2 см"}
      </Text>
      <Pressable style={styles.btn} onPress={() => setOpen(true)}>
        <Text style={styles.btnText}>Відкрити камеру</Text>
      </Pressable>
      <Pressable onPress={() => router.back()}>
        <Text style={styles.link}>← Назад</Text>
      </Pressable>
      <CopyQrScanModal
        visible={open}
        onClose={() => {
          setOpen(false);
          router.back();
        }}
        onScan={onScan}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.screen, padding: 20 },
  h: { fontWeight: "800", fontSize: 20, color: colors.ink, marginBottom: 8 },
  meta: { color: colors.muted, marginBottom: 20, lineHeight: 20 },
  btn: {
    backgroundColor: colors.stamp,
    padding: 14,
    borderRadius: btnRadius,
    marginBottom: 16,
  },
  btnText: { color: "#fff", fontWeight: "800", textAlign: "center" },
  link: { color: colors.stamp, fontWeight: "700" },
});
