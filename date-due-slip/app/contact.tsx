import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  FlatList,
  Image,
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useAuth } from "../src/auth";
import {
  CONTACT_TOPIC_FALLBACK,
  ContactApi,
  getApiBase,
} from "../src/api";
import { CyrillicTextInput } from "../src/CyrillicTextInput";
import { ShelfLogoChip } from "../src/ShelfLogoChip";
import { btnRadius, colors, fs, s } from "../src/theme";

type Shot = { uri: string; name: string; type: string };
type Topic = { value: string; label: string };

export default function Contact() {
  const { user } = useAuth();
  const [topics, setTopics] = useState<Topic[]>(CONTACT_TOPIC_FALLBACK);
  const [topic, setTopic] = useState(CONTACT_TOPIC_FALLBACK[0].value);
  const [topicOpen, setTopicOpen] = useState(false);
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

  const profileName = (user?.username || "").trim();
  const profileEmail = (user?.email || "").trim();

  const topicLabel = useMemo(() => {
    return topics.find((t) => t.value === topic)?.label || topic;
  }, [topics, topic]);

  useEffect(() => {
    ContactApi.config()
      .then((c) => {
        setCfg(c);
        if (c.topics?.length) {
          setTopics(c.topics);
          setTopic((prev) =>
            c.topics!.some((t) => t.value === prev) ? prev : c.topics![0].value
          );
        }
      })
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
    if (!profileName || !profileEmail) {
      Alert.alert(
        "Контакт",
        !profileName
          ? "Немає імені користувача в профілі."
          : "У профілі немає email для відповіді."
      );
      return;
    }
    if (!message.trim()) {
      Alert.alert("Контакт", "Напишіть повідомлення.");
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
      fd.append("subject", `Реченець — контакт: ${topicLabel}`);
      fd.append("from_name", profileName);
      fd.append("name", profileName);
      fd.append("email", profileEmail);
      fd.append(
        "message",
        `Тема: ${topicLabel}\nВід: ${profileName} <${profileEmail}>\nЛогін: ${profileName}\n\n${message.trim()}`
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
      Alert.alert("Контакт", `Надіслано. Відповімо на ${profileEmail}.`);
      setTopic(topics[0]?.value || "bug");
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

      <View style={styles.profileCard}>
        <Text style={styles.profileLabel}>Відправник (з профілю)</Text>
        <Text style={styles.profileLine}>
          <Text style={styles.profileStrong}>@{profileName || "—"}</Text>
          {" · "}
          {profileEmail || (
            <Text style={styles.profileWarn}>немає email у профілі</Text>
          )}
        </Text>
      </View>

      <Text style={styles.label}>Тема</Text>
      <Pressable
        style={styles.select}
        onPress={() => setTopicOpen(true)}
        accessibilityRole="button"
        accessibilityLabel="Тема"
      >
        <Text style={styles.selectText}>{topicLabel}</Text>
        <Text style={styles.selectChevron}>▾</Text>
      </Pressable>

      <Text style={styles.label}>
        Повідомлення ({message.length}/{cfg?.message_max ?? 500})
      </Text>
      <CyrillicTextInput
        style={[styles.input, styles.area]}
        value={message}
        onChangeText={setMessage}
        multiline
      />

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

      <View style={styles.actions}>
        <ShelfLogoChip
          title={`Скріншоти (${shots.length})`}
          icon="add"
          style={styles.actionChip}
          onPress={pickShots}
        />
        <ShelfLogoChip
          title={busy ? "…" : "Надіслати"}
          icon="send"
          style={styles.actionChip}
          disabled={busy}
          onPress={submit}
        />
        <ShelfLogoChip
          title="Веб-форма"
          icon="cloud"
          style={styles.actionChip}
          onPress={openWeb}
        />
      </View>

      <Modal
        visible={topicOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setTopicOpen(false)}
      >
        <Pressable style={styles.modalBackdrop} onPress={() => setTopicOpen(false)}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Тема</Text>
            <FlatList
              data={topics}
              keyExtractor={(item) => item.value}
              keyboardShouldPersistTaps="handled"
              renderItem={({ item }) => {
                const on = item.value === topic;
                return (
                  <Pressable
                    style={[styles.topicRow, on ? styles.topicRowOn : null]}
                    onPress={() => {
                      setTopic(item.value);
                      setTopicOpen(false);
                    }}
                  >
                    <Text style={[styles.topicRowText, on ? styles.topicRowTextOn : null]}>
                      {item.label}
                    </Text>
                  </Pressable>
                );
              }}
            />
          </View>
        </Pressable>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  h: { fontSize: fs(22), fontWeight: "800", color: colors.ink },
  hint: {
    color: colors.muted,
    fontSize: fs(12),
    marginTop: 6,
    marginBottom: 8,
    lineHeight: fs(16),
  },
  profileCard: {
    marginTop: s(10),
    marginBottom: s(4),
    paddingVertical: s(12),
    paddingHorizontal: s(14),
    borderRadius: btnRadius > 24 ? s(14) : btnRadius,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
  },
  profileLabel: { color: colors.muted, fontSize: fs(12), marginBottom: 4 },
  profileLine: { color: colors.ink, fontSize: fs(14), lineHeight: fs(20) },
  profileStrong: { fontWeight: "800" },
  profileWarn: { color: colors.danger, fontWeight: "700" },
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
  select: {
    marginTop: s(6),
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.white,
    borderRadius: btnRadius > 24 ? s(12) : btnRadius,
    paddingHorizontal: s(12),
    paddingVertical: s(12),
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  selectText: { color: colors.ink, fontSize: fs(15), flex: 1 },
  selectChevron: { color: colors.muted, fontSize: fs(14), marginLeft: s(8) },
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: s(10),
    marginTop: s(18),
  },
  actionChip: { flexGrow: 1, flexBasis: "30%" },
  thumbs: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  thumb: {
    width: s(64),
    height: s(64),
    borderRadius: 6,
    backgroundColor: colors.paperDark,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.35)",
    justifyContent: "center",
    paddingHorizontal: s(24),
  },
  modalCard: {
    backgroundColor: colors.white,
    borderRadius: btnRadius > 24 ? s(14) : btnRadius,
    maxHeight: "70%",
    paddingVertical: s(8),
  },
  modalTitle: {
    color: colors.ink,
    fontWeight: "700",
    fontSize: fs(16),
    paddingHorizontal: s(14),
    paddingVertical: s(8),
  },
  topicRow: { paddingHorizontal: s(14), paddingVertical: s(12) },
  topicRowOn: { backgroundColor: colors.paperDark },
  topicRowText: { color: colors.ink, fontSize: fs(15) },
  topicRowTextOn: { fontWeight: "700" },
});
