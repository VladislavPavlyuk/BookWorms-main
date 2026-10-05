import { useEffect, useState } from "react";
import {
  Alert,
  Image,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useAuth } from "../src/auth";
import { ApiError, ContactApi, getApiBase } from "../src/api";
import { CyrillicTextInput } from "../src/CyrillicTextInput";
import { colors, fs, s, btnRadius } from "../src/theme";

type Shot = { uri: string; name: string; type: string };

export default function Contact() {
  const { user } = useAuth();
  const [name, setName] = useState(user?.username || "");
  const [email, setEmail] = useState(user?.email || "");
  const [topic, setTopic] = useState("");
  const [message, setMessage] = useState("");
  const [shots, setShots] = useState<Shot[]>([]);
  const [busy, setBusy] = useState(false);
  const [cfg, setCfg] = useState<{
    access_key: string;
    endpoint: string;
    max_screenshots: number;
    max_file_bytes: number;
    message_max: number;
    to_hint: string;
  } | null>(null);

  useEffect(() => {
    ContactApi.config()
      .then(setCfg)
      .catch(() =>
        setCfg({
          access_key: "",
          endpoint: "https://api.web3forms.com/submit",
          max_screenshots: 10,
          max_file_bytes: 2 * 1024 * 1024,
          message_max: 500,
          to_hint: "vladpavliuk@gmail.com",
        })
      );
  }, []);

  useEffect(() => {
    if (user?.username) setName(user.username);
    if (user?.email) setEmail(user.email);
  }, [user]);

  const pickShots = async () => {
    const max = cfg?.max_screenshots ?? 10;
    if (shots.length >= max) {
      Alert.alert("Скріншоти", `Максимум ${max}.`);
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsMultipleSelection: true,
      quality: 0.85,
      selectionLimit: max - shots.length,
    });
    if (res.canceled) return;
    const next = res.assets.slice(0, max - shots.length).map((a, i) => ({
      uri: a.uri,
      name: a.fileName || `shot_${Date.now()}_${i}.jpg`,
      type: a.mimeType || "image/jpeg",
    }));
    setShots((prev) => [...prev, ...next].slice(0, max));
  };

  const openWeb = async () => {
    const base = (await getApiBase()).replace(/\/$/, "");
    await Linking.openURL(`${base}/contact/`);
  };

  const submit = async () => {
    const messageMax = cfg?.message_max ?? 500;
    if (!name.trim() || !email.trim() || !topic.trim() || !message.trim()) {
      Alert.alert("Контакт", "Заповни ім’я, email, тему і повідомлення.");
      return;
    }
    if (message.length > messageMax) {
      Alert.alert("Контакт", `Максимум ${messageMax} символів.`);
      return;
    }
    if (!cfg?.access_key) {
      Alert.alert("Контакт", "Ключ Web3Forms недоступний — відкрию веб-форму.", [
        { text: "OK", onPress: openWeb },
      ]);
      return;
    }

    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("access_key", cfg.access_key);
      fd.append("subject", `Реченець контакт: ${topic.trim()}`);
      fd.append("from_name", name.trim());
      fd.append("name", name.trim());
      fd.append("email", email.trim());
      fd.append("topic", topic.trim());
      fd.append(
        "message",
        `${message.trim()}\n\n—\nuser: ${user?.username || "anon"} (#${user?.id ?? "?"})`
      );
      shots.forEach((shot, i) => {
        fd.append(`attachment_${i}`, {
          uri: shot.uri,
          name: shot.name,
          type: shot.type,
        } as unknown as Blob);
      });

      const res = await fetch(cfg.endpoint, { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data?.success === false) {
        throw new Error(data?.message || `HTTP ${res.status}`);
      }
      Alert.alert("Контакт", "Надіслано.");
      setTopic("");
      setMessage("");
      setShots([]);
    } catch (e) {
      Alert.alert(
        "Контакт",
        `${e instanceof Error ? e.message : String(e)}\n\nВідкрити веб-форму?`,
        [
          { text: "Скасувати", style: "cancel" },
          { text: "Веб", onPress: openWeb },
        ]
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.screen }}
      contentContainerStyle={{ padding: 20 }}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.h}>Контакт з розробниками</Text>
      <Text style={styles.hint}>
        Через Web3Forms → {cfg?.to_hint || "…"}. До {cfg?.max_screenshots ?? 10}{" "}
        скріншотів, текст до {cfg?.message_max ?? 500} символів.
      </Text>

      <Text style={styles.label}>Ім’я</Text>
      <CyrillicTextInput style={styles.input} value={name} onChangeText={setName} />

      <Text style={styles.label}>Email</Text>
      <CyrillicTextInput
        style={styles.input}
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
      />

      <Text style={styles.label}>Тема</Text>
      <CyrillicTextInput style={styles.input} value={topic} onChangeText={setTopic} />

      <Text style={styles.label}>
        Повідомлення ({message.length}/{cfg?.message_max ?? 500})
      </Text>
      <CyrillicTextInput
        style={[styles.input, styles.area]}
        value={message}
        onChangeText={setMessage}
        multiline
      />

      <Pressable style={styles.rowBtn} onPress={pickShots}>
        <Text style={styles.rowBtnText}>Додати скріншоти ({shots.length})</Text>
      </Pressable>
      <View style={styles.thumbs}>
        {shots.map((shot) => (
          <Pressable
            key={shot.uri}
            onPress={() => setShots((prev) => prev.filter((x) => x.uri !== shot.uri))}
          >
            <Image source={{ uri: shot.uri }} style={styles.thumb} />
          </Pressable>
        ))}
      </View>

      <Pressable
        style={[styles.btn, busy && { opacity: 0.6 }]}
        onPress={submit}
        disabled={busy}
      >
        <Text style={styles.btnText}>{busy ? "Надсилаю…" : "Надіслати"}</Text>
      </Pressable>
      <Pressable onPress={openWeb}>
        <Text style={styles.link}>Відкрити веб-форму</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  h: { fontSize: fs(22), fontWeight: "800", color: colors.ink },
  hint: { color: colors.muted, fontSize: fs(12), marginTop: 6, marginBottom: 8, lineHeight: fs(16) },
  label: { marginTop: s(14), color: colors.muted, fontSize: fs(12) },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: s(12),
    fontSize: fs(16),
    minHeight: s(48),
  },
  area: { minHeight: s(120), textAlignVertical: "top" },
  rowBtn: { marginTop: s(16), paddingVertical: s(12), borderBottomWidth: 1, borderColor: colors.line },
  rowBtnText: { color: colors.ink, fontWeight: "700", fontSize: fs(15) },
  thumbs: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  thumb: { width: s(64), height: s(64), borderRadius: 6, backgroundColor: colors.paperDark },
  btn: {
    backgroundColor: colors.ink,
    padding: s(14),
    marginTop: s(20),
    minHeight: s(54),
    borderRadius: btnRadius,
  },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700", fontSize: fs(16) },
  link: {
    color: colors.muted,
    textAlign: "center",
    marginTop: s(14),
    fontWeight: "700",
    fontSize: fs(14),
  },
});
