import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import * as ImagePicker from "expo-image-picker";
import { useAuth } from "../../src/auth";
import { ApiError, AuthApi, BooksApi, getApiBase, setApiBase } from "../../src/api";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import type { UserSubProfile } from "../../src/types";
import { ShelfLogoChip } from "../../src/ShelfLogoChip";
import { colors, fs, s, btnRadius } from "../../src/theme";
import { useUnread } from "../../src/unread";

const MAX_SUBPROFILES = 8;

export default function More() {
  const { user, logout, reload } = useAuth();
  const { unread, pollError, refresh } = useUnread();
  const router = useRouter();
  const [api, setApi] = useState("");
  const [username, setUsername] = useState(user?.username || "");
  const [biography, setBiography] = useState(user?.biography || "");
  const [age, setAge] = useState(user?.age != null ? String(user.age) : "");
  const [place, setPlace] = useState(user?.place || "");
  const [themes, setThemes] = useState<string[]>(user?.preferred_subjects || []);
  const [catalogThemes, setCatalogThemes] = useState<string[]>([]);
  const [subprofiles, setSubprofiles] = useState<UserSubProfile[]>(user?.subprofiles || []);
  const [editing, setEditing] = useState(false);
  const [avatarLocal, setAvatarLocal] = useState<string | null>(null);
  const [subDraft, setSubDraft] = useState<{
    id?: number;
    name: string;
    age: string;
    place: string;
    preferred_subjects: string[];
  } | null>(null);

  useEffect(() => {
    getApiBase().then(setApi);
  }, []);

  useEffect(() => {
    setUsername(user?.username || "");
    setBiography(user?.biography || "");
    setAge(user?.age != null ? String(user.age) : "");
    setPlace(user?.place || "");
    setThemes(user?.preferred_subjects || []);
    setSubprofiles(user?.subprofiles || []);
    setAvatarLocal(null);
  }, [user]);

  useEffect(() => {
    if (!editing && !subDraft) return;
    let cancelled = false;
    BooksApi.subjects()
      .then((r) => {
        if (!cancelled) setCatalogThemes(r.subjects || []);
      })
      .catch(() => {
        if (!cancelled) setCatalogThemes([]);
      });
    return () => {
      cancelled = true;
    };
  }, [editing, subDraft]);

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

  const parseAge = (raw: string): number | null => {
    const t = raw.trim();
    if (!t) return null;
    const n = parseInt(t, 10);
    if (Number.isNaN(n) || n < 0 || n > 120) return null;
    return n;
  };

  const saveProfile = async () => {
    try {
      const ageVal = age.trim() === "" ? null : parseAge(age);
      if (age.trim() && ageVal === null) {
        Alert.alert("Профіль", "Вік: 0–120.");
        return;
      }
      if (avatarLocal) {
        const fd = new FormData();
        fd.append("username", username.trim());
        fd.append("biography", biography);
        if (ageVal !== null) fd.append("age", String(ageVal));
        else fd.append("age", "");
        fd.append("place", place.trim());
        fd.append("preferred_subjects", JSON.stringify(themes));
        fd.append("avatar", {
          uri: avatarLocal,
          name: "avatar.jpg",
          type: "image/jpeg",
        } as unknown as Blob);
        await AuthApi.updateMe(fd);
      } else {
        await AuthApi.updateMe({
          username: username.trim(),
          biography,
          age: ageVal,
          place: place.trim(),
          preferred_subjects: themes,
        });
      }
      await reload();
      setEditing(false);
      setAvatarLocal(null);
      Alert.alert("Профіль", "Збережено.");
    } catch (e) {
      Alert.alert("Профіль", e instanceof ApiError ? e.message : String(e));
    }
  };

  const toggleTheme = (theme: string, list: string[], setList: (v: string[]) => void) => {
    const key = theme.toLowerCase();
    const has = list.some((t) => t.toLowerCase() === key);
    if (has) setList(list.filter((t) => t.toLowerCase() !== key));
    else setList([...list, theme]);
  };

  const themeChoices = (() => {
    const map = new Map<string, string>();
    for (const t of catalogThemes) map.set(t.toLowerCase(), t);
    for (const t of themes) {
      if (t && !map.has(t.toLowerCase())) map.set(t.toLowerCase(), t);
    }
    if (subDraft) {
      for (const t of subDraft.preferred_subjects) {
        if (t && !map.has(t.toLowerCase())) map.set(t.toLowerCase(), t);
      }
    }
    return [...map.values()].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  })();

  const saveSubprofile = async () => {
    if (!subDraft) return;
    const name = subDraft.name.trim();
    if (!name) {
      Alert.alert("Підпрофіль", "Назва обов’язкова.");
      return;
    }
    const ageVal = subDraft.age.trim() === "" ? null : parseAge(subDraft.age);
    if (subDraft.age.trim() && ageVal === null) {
      Alert.alert("Підпрофіль", "Вік: 0–120.");
      return;
    }
    try {
      if (subDraft.id) {
        await AuthApi.updateSubprofile(subDraft.id, {
          name,
          age: ageVal,
          place: subDraft.place.trim(),
          preferred_subjects: subDraft.preferred_subjects,
        });
      } else {
        await AuthApi.createSubprofile({
          name,
          age: ageVal,
          place: subDraft.place.trim(),
          preferred_subjects: subDraft.preferred_subjects,
        });
      }
      await reload();
      setSubDraft(null);
      Alert.alert("Підпрофіль", "Збережено.");
    } catch (e) {
      Alert.alert("Підпрофіль", e instanceof ApiError ? e.message : String(e));
    }
  };

  const deleteSubprofile = (sp: UserSubProfile) => {
    Alert.alert("Видалити підпрофіль?", sp.name, [
      { text: "Скасувати", style: "cancel" },
      {
        text: "Видалити",
        style: "destructive",
        onPress: async () => {
          try {
            await AuthApi.deleteSubprofile(sp.id);
            await reload();
          } catch (e) {
            Alert.alert("Підпрофіль", e instanceof ApiError ? e.message : String(e));
          }
        },
      },
    ]);
  };

  const avatarUri = avatarLocal || user?.avatar_url || null;

  const ThemeBoxes = ({
    selected,
    onToggle,
  }: {
    selected: string[];
    onToggle: (theme: string) => void;
  }) => (
    <View style={styles.themeGrid}>
      {themeChoices.length === 0 ? (
        <Text style={styles.hint}>Немає тем у каталозі — з’являться після книг із subjects.</Text>
      ) : (
        themeChoices.map((theme) => {
          const on = selected.some((t) => t.toLowerCase() === theme.toLowerCase());
          return (
            <Pressable
              key={theme}
              style={[styles.themeChip, on ? styles.themeChipOn : null]}
              onPress={() => onToggle(theme)}
            >
              <Text style={[styles.themeChipText, on ? styles.themeChipTextOn : null]}>
                {on ? "☑ " : "☐ "}
                {theme}
              </Text>
            </Pressable>
          );
        })
      )}
    </View>
  );

  if (subDraft) {
    return (
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.screen }}
        contentContainerStyle={{ padding: 20 }}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.sectionTitle}>
          {subDraft.id ? "Редагувати підпрофіль" : "Новий підпрофіль"}
        </Text>
        <Text style={styles.label}>Назва</Text>
        <CyrillicTextInput
          style={styles.input}
          value={subDraft.name}
          onChangeText={(t) => setSubDraft({ ...subDraft, name: t })}
          placeholder="напр. Для сина"
          placeholderTextColor={colors.muted}
        />
        <Text style={styles.label}>Вік</Text>
        <CyrillicTextInput
          style={styles.input}
          value={subDraft.age}
          onChangeText={(t) => setSubDraft({ ...subDraft, age: t.replace(/[^\d]/g, "").slice(0, 3) })}
          keyboardType="number-pad"
          placeholder="років"
          placeholderTextColor={colors.muted}
        />
        <Text style={styles.label}>Місце проживання</Text>
        <CyrillicTextInput
          style={styles.input}
          value={subDraft.place}
          onChangeText={(t) => setSubDraft({ ...subDraft, place: t })}
          placeholder="місто / країна"
          placeholderTextColor={colors.muted}
        />
        <Text style={styles.label}>Теми / жанри</Text>
        <ThemeBoxes
          selected={subDraft.preferred_subjects}
          onToggle={(theme) =>
            setSubDraft({
              ...subDraft,
              preferred_subjects: (() => {
                const key = theme.toLowerCase();
                const has = subDraft.preferred_subjects.some((t) => t.toLowerCase() === key);
                return has
                  ? subDraft.preferred_subjects.filter((t) => t.toLowerCase() !== key)
                  : [...subDraft.preferred_subjects, theme];
              })(),
            })
          }
        />
        <ShelfLogoChip
          title="Зберегти підпрофіль"
          icon="check"
          style={styles.chip}
          onPress={saveSubprofile}
        />
        <ShelfLogoChip
          title="Скасувати"
          icon="close"
          style={[styles.chip, { marginTop: 10 }]}
          onPress={() => setSubDraft(null)}
        />
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.screen }}
      contentContainerStyle={{ padding: 20 }}
      keyboardShouldPersistTaps="handled"
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
          <Text style={styles.label}>Вік</Text>
          <CyrillicTextInput
            style={styles.input}
            value={age}
            onChangeText={(t) => setAge(t.replace(/[^\d]/g, "").slice(0, 3))}
            keyboardType="number-pad"
            placeholder="років"
            placeholderTextColor={colors.muted}
          />
          <Text style={styles.label}>Місце проживання</Text>
          <CyrillicTextInput
            style={styles.input}
            value={place}
            onChangeText={setPlace}
            placeholder="місто / країна"
            placeholderTextColor={colors.muted}
          />
          <Text style={styles.label}>Теми / жанри</Text>
          <Text style={styles.hint}>Список з каталогу книг — оновлюється автоматично.</Text>
          <ThemeBoxes selected={themes} onToggle={(theme) => toggleTheme(theme, themes, setThemes)} />
          <ShelfLogoChip
            title="Зберегти профіль"
            icon="check"
            style={styles.chip}
            onPress={saveProfile}
          />
          <ShelfLogoChip
            title="Скасувати"
            icon="close"
            style={[styles.chip, { marginTop: 10 }]}
            onPress={() => {
              setEditing(false);
              setAvatarLocal(null);
            }}
          />
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
          <Text style={styles.meta}>
            Вік: {user?.age != null ? user.age : "—"} · Місце: {user?.place || "—"}
          </Text>
          {(user?.preferred_subjects || []).length > 0 ? (
            <Text style={styles.meta}>Теми: {(user?.preferred_subjects || []).join(", ")}</Text>
          ) : (
            <Text style={styles.meta}>Теми: не обрано</Text>
          )}
          <Pressable style={styles.row} onPress={() => setEditing(true)}>
            <Text style={styles.rowText}>Редагувати профіль</Text>
          </Pressable>
        </>
      )}

      <Text style={styles.sectionTitle}>Підпрофілі</Text>
      <Text style={styles.hint}>
        Для книг іншій людині. Стрічка = пости під ваш профіль або будь-який підпрофіль.
      </Text>
      {subprofiles.map((sp) => (
        <View key={sp.id} style={styles.subCard}>
          <Text style={styles.subName}>{sp.name}</Text>
          <Text style={styles.meta}>
            Вік: {sp.age != null ? sp.age : "—"} · {sp.place || "—"}
          </Text>
          {(sp.preferred_subjects || []).length > 0 ? (
            <Text style={styles.meta}>{sp.preferred_subjects.join(", ")}</Text>
          ) : null}
          <View style={styles.subActions}>
            <Pressable
              onPress={() =>
                setSubDraft({
                  id: sp.id,
                  name: sp.name,
                  age: sp.age != null ? String(sp.age) : "",
                  place: sp.place || "",
                  preferred_subjects: sp.preferred_subjects || [],
                })
              }
            >
              <Text style={styles.link}>Редагувати</Text>
            </Pressable>
            <Pressable onPress={() => deleteSubprofile(sp)}>
              <Text style={[styles.link, { color: colors.stamp }]}>Видалити</Text>
            </Pressable>
          </View>
        </View>
      ))}
      {subprofiles.length < MAX_SUBPROFILES ? (
        <Pressable
          style={styles.row}
          onPress={() =>
            setSubDraft({ name: "", age: "", place: "", preferred_subjects: [] })
          }
        >
          <Text style={styles.rowText}>+ Додати підпрофіль</Text>
        </Pressable>
      ) : (
        <Text style={styles.hint}>Ліміт підпрофілів ({MAX_SUBPROFILES}).</Text>
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
      <ShelfLogoChip
        title="Зберегти URL"
        icon="cloud"
        style={styles.chip}
        onPress={saveApi}
      />
      <ShelfLogoChip
        title="Вийти"
        icon="trash"
        danger
        style={[styles.chip, { marginTop: 24 }]}
        onPress={logout}
      />
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
  avatarEmpty: {
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
  },
  avatarPlus: { fontSize: fs(28), color: colors.muted, fontWeight: "700" },
  avatarLetter: { fontSize: fs(32), color: colors.ink, fontWeight: "800" },
  avatarHint: { marginTop: 6, color: colors.muted, fontSize: fs(12), fontWeight: "600" },
  name: { fontSize: fs(22), fontWeight: "800", color: colors.ink, textAlign: "center" },
  bio: { color: colors.muted, marginTop: 4, fontSize: fs(15), textAlign: "center" },
  email: {
    color: colors.muted,
    fontSize: fs(12),
    marginBottom: s(8),
    marginTop: 2,
    textAlign: "center",
  },
  meta: {
    color: colors.muted,
    fontSize: fs(13),
    textAlign: "center",
    marginBottom: 4,
  },
  sectionTitle: {
    marginTop: s(20),
    marginBottom: 4,
    fontSize: fs(17),
    fontWeight: "800",
    color: colors.ink,
  },
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
  label: { marginTop: s(16), color: colors.muted, fontSize: fs(12) },
  hint: { color: colors.muted, fontSize: fs(11), marginTop: 4, lineHeight: fs(15) },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: s(12),
    fontSize: fs(16),
    minHeight: s(48),
  },
  chip: { marginTop: s(12), alignSelf: "stretch" },
  themeGrid: { marginTop: 8, gap: 6 },
  themeChip: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: btnRadius,
    paddingVertical: 8,
    paddingHorizontal: 10,
    backgroundColor: colors.paperDark,
  },
  themeChipOn: { borderColor: colors.ink, backgroundColor: colors.ink },
  themeChipText: { color: colors.ink, fontSize: fs(13), fontWeight: "600" },
  themeChipTextOn: { color: colors.white },
  subCard: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    paddingVertical: s(12),
  },
  subName: { color: colors.ink, fontWeight: "700", fontSize: fs(15) },
  subActions: { flexDirection: "row", gap: 16, marginTop: 8 },
  link: { color: colors.ink, fontWeight: "700", fontSize: fs(13) },
});
