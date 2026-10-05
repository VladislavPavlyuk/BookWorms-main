import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import * as ImagePicker from "expo-image-picker";
import { useAuth } from "../../src/auth";
import { ApiError, AuthApi, getApiBase, setApiBase } from "../../src/api";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { colors, fs, s, btnRadius } from "../../src/theme";
import { useUnread } from "../../src/unread";

export default function More() {
  const { user, logout, reload } = useAuth();
  const { unread, pollError, refresh } = useUnread();
  const router = useRouter();
  const [api, setApi] = useState("");
  const [username, setUsername] = useState(user?.username || "");
  const [biography, setBiography] = useState(user?.biography || "");
  const [editing, setEditing] = useState(false);
  const [avatarLocal, setAvatarLocal] = useState<string | null>(null);

  useEffect(() => {
    getApiBase().then(setApi);
  }, []);

  useEffect(() => {
    setUsername(user?.username || "");
    setBiography(user?.biography || "");
    setAvatarLocal(null);
  }, [user]);

  const saveApi = async () => {
    await setApiBase(api.trim());
    const next = await getApiBase();
    setApi(next);
    await refresh();
    Alert.alert("API", `Збережено:\n${next}\nПерелогінься якщо токен від іншого хоста.`);
  };

  const pickAvatar = async () => {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.85,
    });
    if (res.canceled || !res.assets?.[0]) return;
    setAvatarLocal(res.assets[0].uri);
  };

  const saveProfile = async () => {
    try {
      if (avatarLocal) {
        const fd = new FormData();
        fd.append("username", username.trim());
        fd.append("biography", biography);
        fd.append("avatar", {
          uri: avatarLocal,
          name: "avatar.jpg",
          type: "image/jpeg",
        } as unknown as Blob);
        await AuthApi.updateMe(fd);
      } else {
        await AuthApi.updateMe({ username: username.trim(), biography });
      }
      await reload();
      setEditing(false);
      setAvatarLocal(null);
      Alert.alert("Профіль", "Збережено.");
    } catch (e) {
      Alert.alert("Профіль", e instanceof ApiError ? e.message : String(e));
    }
  };

  const avatarUri = avatarLocal || user?.avatar_url || null;

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.screen }}
      contentContainerStyle={{ padding: 20 }}
    >
      {editing ? (
        <>
          <Pressable style={styles.avatarWrap} onPress={pickAvatar}>
            {avatarUri ? (
              <Image source={{ uri: avatarUri }} style={styles.avatar} />
            ) : (
              <View style={[styles.avatar, styles.avatarEmpty]}>
                <Text style={styles.avatarPlus}>+</Text>
              </View>
            )}
            <Text style={styles.avatarHint}>Змінити аватар</Text>
          </Pressable>
          <Text style={styles.label}>Логін</Text>
          <CyrillicTextInput
            style={styles.input}
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            keyboardType="default"
            textContentType="username"
          />
          <Text style={styles.label}>Про себе</Text>
          <CyrillicTextInput
            style={styles.input}
            value={biography}
            onChangeText={setBiography}
            multiline
            autoCapitalize="sentences"
            keyboardType="default"
          />
          <Pressable style={styles.btn} onPress={saveProfile}>
            <Text style={styles.btnText}>Зберегти профіль</Text>
          </Pressable>
          <Pressable onPress={() => { setEditing(false); setAvatarLocal(null); }}>
            <Text style={styles.cancel}>Скасувати</Text>
          </Pressable>
        </>
      ) : (
        <>
          <View style={styles.avatarWrap}>
            {avatarUri ? (
              <Image source={{ uri: avatarUri }} style={styles.avatar} />
            ) : (
              <View style={[styles.avatar, styles.avatarEmpty]}>
                <Text style={styles.avatarLetter}>
                  {(user?.username || "?").slice(0, 1).toUpperCase()}
                </Text>
              </View>
            )}
          </View>
          <Text style={styles.name}>{user?.username}</Text>
          <Text style={styles.bio}>{user?.biography || "немає біографії"}</Text>
          <Text style={styles.email}>{user?.email}</Text>
          <Pressable style={styles.row} onPress={() => setEditing(true)}>
            <Text style={styles.rowText}>Редагувати профіль</Text>
          </Pressable>
        </>
      )}

      {user && (
        <Pressable style={styles.row} onPress={() => router.push(`/user/${user.id}`)}>
          <Text style={styles.rowText}>Моя публічна полиця</Text>
        </Pressable>
      )}
      <Pressable style={styles.row} onPress={() => router.push("/notifications")}>
        <View style={styles.rowInner}>
          <Text style={styles.rowText}>Сповіщення</Text>
          {unread > 0 ? (
            <View style={styles.rowBadge}>
              <Text style={styles.rowBadgeText}>{unread > 99 ? "99+" : unread}</Text>
            </View>
          ) : null}
        </View>
      </Pressable>
      <Pressable style={styles.row} onPress={() => router.push("/exchanges")}>
        <Text style={styles.rowText}>Обміни / позики / чати</Text>
      </Pressable>
      <Pressable style={styles.row} onPress={() => router.push("/queues")}>
        <Text style={styles.rowText}>Мої черги</Text>
      </Pressable>
      <Pressable style={styles.row} onPress={() => router.push("/contact")}>
        <Text style={styles.rowText}>Контакт з розробниками</Text>
      </Pressable>
      <Pressable
        style={styles.row}
        onPress={() =>
          Alert.alert("Створити пост", undefined, [
            {
              text: "Подія",
              onPress: () => router.push({ pathname: "/post/new", params: { mode: "event" } }),
            },
            {
              text: "Відгук про книгу",
              onPress: () =>
                router.push({ pathname: "/post/new", params: { mode: "feedback" } }),
            },
            { text: "Скасувати", style: "cancel" },
          ])
        }
      >
        <Text style={styles.rowText}>Новий пост</Text>
      </Pressable>

      <Text style={styles.label}>API (NAS)</Text>
      <CyrillicTextInput
        style={styles.input}
        value={api}
        onChangeText={setApi}
        autoCapitalize="none"
        keyboardType="default"
      />
      <Text style={styles.hint}>
        Має бути http://192.168.0.213:18088 (та сама Wi‑Fi, що NAS). Unread: {unread}
        {pollError ? `\nБейдж: помилка — ${pollError}` : " · poll ok"}
      </Text>
      <Pressable style={styles.btn} onPress={saveApi}>
        <Text style={styles.btnText}>Зберегти URL</Text>
      </Pressable>
      <Pressable
        style={[styles.btn, { backgroundColor: colors.stamp, marginTop: 24 }]}
        onPress={logout}
      >
        <Text style={styles.btnText}>Вийти</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  avatarWrap: { alignItems: "center", marginBottom: s(12) },
  avatar: {
    width: s(88),
    height: s(88),
    borderRadius: s(44),
    backgroundColor: colors.paperDark,
  },
  avatarEmpty: { alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: colors.line },
  avatarPlus: { fontSize: fs(28), color: colors.muted, fontWeight: "700" },
  avatarLetter: { fontSize: fs(32), color: colors.ink, fontWeight: "800" },
  avatarHint: { marginTop: 6, color: colors.muted, fontSize: fs(12), fontWeight: "600" },
  name: { fontSize: fs(22), fontWeight: "800", color: colors.ink, textAlign: "center" },
  bio: { color: colors.muted, marginTop: 4, fontSize: fs(15), textAlign: "center" },
  email: { color: colors.muted, fontSize: fs(12), marginBottom: s(16), marginTop: 2, textAlign: "center" },
  row: { borderBottomWidth: 1, borderColor: colors.line, paddingVertical: s(14) },
  rowInner: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  rowText: { color: colors.ink, fontSize: fs(16), fontWeight: "600" },
  rowBadge: {
    minWidth: s(22),
    height: s(22),
    borderRadius: s(11),
    backgroundColor: "#E53935",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 6,
  },
  rowBadgeText: { color: "#fff", fontSize: fs(12), fontWeight: "800" },
  label: { marginTop: s(20), color: colors.muted, fontSize: fs(12) },
  hint: { color: colors.muted, fontSize: fs(11), marginTop: 6, lineHeight: fs(15) },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: s(12),
    fontSize: fs(16),
    minHeight: s(48),
  },
  btn: { backgroundColor: colors.ink, padding: s(14), marginTop: s(12), minHeight: s(54), borderRadius: btnRadius },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700", fontSize: fs(16) },
  cancel: {
    color: colors.muted,
    textAlign: "center",
    marginTop: s(12),
    fontWeight: "700",
  },
});
