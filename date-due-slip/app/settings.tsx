import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { colors, btnRadius } from "../src/theme";

export default function SettingsScreen() {
  const router = useRouter();
  return (
    <View style={styles.root}>
      <Text style={styles.h}>Налаштування</Text>
      <Text style={styles.meta}>Сервіси облікового запису Date Due Slip.</Text>

      <Pressable
        style={styles.card}
        onPress={() => router.push("/qr-print?from=settings")}
      >
        <Text style={styles.cardTitle}>Друкувати QR коди</Text>
        <Text style={styles.cardBody}>
          Унікальні QR 20×20 мм для примірників, заголовок www.datedueslip.com, пунктирна сітка
          (точний A4 — у веб-версії Налаштування → Друкувати QR коди).
        </Text>
      </Pressable>

      <Pressable onPress={() => router.back()}>
        <Text style={styles.link}>← Назад</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.screen, padding: 20 },
  h: { fontWeight: "800", fontSize: 22, color: colors.ink, marginBottom: 8 },
  meta: { color: colors.muted, marginBottom: 20, lineHeight: 20 },
  card: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
    padding: 16,
    borderRadius: btnRadius,
    marginBottom: 24,
  },
  cardTitle: { fontWeight: "800", color: colors.ink, fontSize: 16, marginBottom: 6 },
  cardBody: { color: colors.muted, lineHeight: 20, fontSize: 13 },
  link: { color: colors.stamp, fontWeight: "700" },
});
