import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, View } from "react-native";
import { useRouter } from "expo-router";
import {
  isNotifySoundEnabled,
  setNotifySoundEnabled,
} from "../src/notifySound";
import { ShelfLogoChip } from "../src/ShelfLogoChip";
import { colors, btnRadius, s } from "../src/theme";

export default function SettingsScreen() {
  const router = useRouter();
  const [soundOn, setSoundOn] = useState(true);

  useEffect(() => {
    isNotifySoundEnabled().then(setSoundOn);
  }, []);

  return (
    <View style={styles.root}>
      <Text style={styles.h}>Налаштування</Text>
      <Text style={styles.meta}>Сервіси облікового запису Date Due Slip.</Text>

      <View style={styles.card}>
        <View style={styles.row}>
          <View style={styles.rowText}>
            <Text style={styles.cardTitle}>Звук сповіщень</Text>
            <Text style={styles.cardBody}>
              Вібрація при нових непрочитаних сповіщеннях.
            </Text>
          </View>
          <Switch
            value={soundOn}
            onValueChange={(v) => {
              setSoundOn(v);
              setNotifySoundEnabled(v);
            }}
            trackColor={{ false: colors.line, true: colors.stampOk }}
            thumbColor={colors.white}
          />
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Спільна бібліотека</Text>
        <Text style={styles.cardBody}>
          Об’єднання полиць, код merge, голосування за адміна, поділ.
        </Text>
        <ShelfLogoChip
          title="Спільна бібліотека"
          icon="library"
          style={styles.chip}
          onPress={() => router.push("/library")}
        />
      </View>

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
    marginBottom: 16,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  rowText: { flex: 1, minWidth: 0 },
  cardTitle: { fontWeight: "800", color: colors.ink, fontSize: 16, marginBottom: 6 },
  cardBody: { color: colors.muted, lineHeight: 20, fontSize: 13 },
  chip: { alignSelf: "flex-start", marginTop: s(12) },
  link: { color: colors.stamp, fontWeight: "700", marginTop: 8 },
});
