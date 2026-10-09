import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { useAuth } from "../../src/auth";
import { ApiError, AuthApi, BooksApi, getApiBase, setApiBase } from "../../src/api";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { useResolvedMediaUrl } from "../../src/mediaUrl";
import type { UserSubProfile } from "../../src/types";
import { ShelfLogoChip } from "../../src/ShelfLogoChip";
import { colors, fs, s, btnRadius } from "../../src/theme";
import { useUnread } from "../../src/unread";

const MAX_SUBPROFILES = 8;

type AvatarOpt = { id: number; name: string; image_url: string };

function AvatarImg({ uri, style }: { uri: string | null; style: object }) {
  const src = useResolvedMediaUrl(uri);
  if (!src) return null;
  return <Image source={{ uri: src }} style={style} />;
}

export default function More() {
  const { user, logout, reload } = useAuth();
  const { unread, pollError, refresh } = useUnread();
  const router = useRouter();
  const [api, setApi] = useState("");
  const [username, setUsername] = useState(user?.username || "");
  const [biography, setBiography] = useState(user?.biography || "");
  const [birthday, setBirthday] = useState(user?.birthday || "");
  const [place, setPlace] = useState(user?.place || "");
  const [themes, setThemes] = useState<string[]>(user?.preferred_subjects || []);
  const [catalogThemes, setCatalogThemes] = useState<string[]>([]);
  const [subprofiles, setSubprofiles] = useState<UserSubProfile[]>(user?.subprofiles || []);
  const [editing, setEditing] = useState(false);
  const [avatars, setAvatars] = useState<AvatarOpt[]>([]);
  const [avatarChoice, setAvatarChoice] = useState<number | null>(null);
  const [subDraft, setSubDraft] = useState<{
    id?: number;
    name: string;
    birthday: string;
    place: string;
    preferred_subjects: string[];
  } | null>(null);

  const canAddSub = subprofiles.length < MAX_SUBPROFILES;
  const avatarUri = user?.avatar_url || null;

  useEffect(() => {
    getApiBase().then(setApi);
  }, []);

  useEffect(() => {
    setUsername(user?.username || "");
    setBiography(user?.biography || "");
    setBirthday(user?.birthday || "");
    setPlace(user?.place || "");
    setThemes(user?.preferred_subjects || []);
    setSubprofiles(user?.subprofiles || []);
    setAvatarChoice(null);
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

  useEffect(() => {
    if (!editing) return;
    let cancelled = false;
    AuthApi.avatars()
      .then((r) => {
        if (!cancelled) setAvatars(r.results || []);
      })
      .catch(() => {
        if (!cancelled) setAvatars([]);
      });
    return () => {
      cancelled = true;
    };
  }, [editing]);

  const saveApi = async () => {
    await setApiBase(api.trim());
    const next = await getApiBase();
    setApi(next);
    await refresh();
    Alert.alert("API", `Збережено:\n${next}\nПерелогінься якщо токен від іншого хоста.`);
  };

  const parseBirthday = (raw: string): string | null | false => {
    const t = raw.trim();
    if (!t) return null;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return false;
    const d = new Date(`${t}T00:00:00`);
    if (Number.isNaN(d.getTime())) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (d > today) return false;
    return t;
  };

  const formatBday = (iso: string | null | undefined) => {
    if (!iso) return "";
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    return m ? `${m[3]}.${m[2]}.${m[1]}` : iso;
  };

  const saveProfile = async () => {
    try {
      const bday = parseBirthday(birthday);
      if (bday === false) {
        Alert.alert("Профіль", "Дата народження: РРРР-ММ-ДД, не в майбутньому.");
        return;
      }
      await AuthApi.updateMe({
        username: username.trim(),
        biography,
        birthday: bday,
        place: place.trim(),
        preferred_subjects: themes,
        ...(avatarChoice != null ? { avatar_choice: avatarChoice } : {}),
      });
      await reload();
      setEditing(false);
      setAvatarChoice(null);
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
    const bday = parseBirthday(subDraft.birthday);
    if (bday === false) {
      Alert.alert("Підпрофіль", "Дата народження: РРРР-ММ-ДД, не в майбутньому.");
      return;
    }
    try {
      if (subDraft.id) {
        await AuthApi.updateSubprofile(subDraft.id, {
          name,
          birthday: bday,
          place: subDraft.place.trim(),
          preferred_subjects: subDraft.preferred_subjects,
        });
      } else {
        await AuthApi.createSubprofile({
          name,
          birthday: bday,
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

  const startEdit = () => {
    setUsername(user?.username || "");
    setBiography(user?.biography || "");
    setBirthday(user?.birthday || "");
    setPlace(user?.place || "");
    setThemes(user?.preferred_subjects || []);
    setAvatarChoice(null);
    setEditing(true);
  };

  const emptySubDraft = () =>
    setSubDraft({ name: "", birthday: "", place: "", preferred_subjects: [] });

  const editSubDraft = (sp: UserSubProfile) =>
    setSubDraft({
      id: sp.id,
      name: sp.name,
      birthday: sp.birthday || "",
      place: sp.place || "",
      preferred_subjects: sp.preferred_subjects || [],
    });

  const ThemeBoxes = ({
    selected,
    onToggle,
  }: {
    selected: string[];
    onToggle: (theme: string) => void;
  }) => (
    <View style={styles.themeGrid}>
      {themeChoices.length === 0 ? (
        <Text style={styles.hint}>
          У каталозі ще немає тем — з’являться після додавання книг із subjects.
        </Text>
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
        <Text style={styles.pageTitle}>
          {subDraft.id ? `Редагувати: ${subDraft.name}` : "Новий підпрофіль"}
        </Text>
        <Text style={styles.label}>Назва</Text>
        <CyrillicTextInput
          style={styles.input}
          value={subDraft.name}
          onChangeText={(t) => setSubDraft({ ...subDraft, name: t })}
          placeholder="напр. Для сина"
          placeholderTextColor={colors.muted}
        />
        <View style={styles.row2}>
          <View style={styles.colAge}>
            <Text style={styles.label}>Дата народження</Text>
            <CyrillicTextInput
              style={styles.input}
              value={subDraft.birthday}
              onChangeText={(t) =>
                setSubDraft({
                  ...subDraft,
                  birthday: t.replace(/[^\d-]/g, "").slice(0, 10),
                })
              }
              keyboardType="numbers-and-punctuation"
              placeholder="РРРР-ММ-ДД"
              placeholderTextColor={colors.muted}
              autoCapitalize="none"
            />
          </View>
          <View style={styles.colPlace}>
            <Text style={styles.label}>Місце проживання</Text>
            <CyrillicTextInput
              style={styles.input}
              value={subDraft.place}
              onChangeText={(t) => setSubDraft({ ...subDraft, place: t })}
              placeholder="місто / країна"
              placeholderTextColor={colors.muted}
            />
          </View>
        </View>
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
        <View style={styles.actions}>
          <ShelfLogoChip
            title="Зберегти"
            icon="check"
            style={styles.actionChip}
            onPress={saveSubprofile}
          />
          <ShelfLogoChip
            title="Назад до профілю"
            icon="close"
            style={styles.actionChip}
            onPress={() => setSubDraft(null)}
          />
        </View>
      </ScrollView>
    );
  }

  if (editing) {
    return (
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.screen }}
        contentContainerStyle={{ padding: 20 }}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.pageTitle}>Редагувати профіль</Text>

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
          style={[styles.input, styles.bioInput]}
          value={biography}
          onChangeText={setBiography}
          multiline
          autoCapitalize="sentences"
          keyboardType="default"
        />

        <View style={styles.row2}>
          <View style={styles.colAge}>
            <Text style={styles.label}>Дата народження</Text>
            <CyrillicTextInput
              style={styles.input}
              value={birthday}
              onChangeText={(t) => setBirthday(t.replace(/[^\d-]/g, "").slice(0, 10))}
              keyboardType="numbers-and-punctuation"
              placeholder="РРРР-ММ-ДД"
              placeholderTextColor={colors.muted}
              autoCapitalize="none"
            />
            {user?.age != null ? (
              <Text style={styles.hint}>Зараз: {user.age} р.</Text>
            ) : null}
          </View>
          <View style={styles.colPlace}>
            <Text style={styles.label}>Місце проживання</Text>
            <CyrillicTextInput
              style={styles.input}
              value={place}
              onChangeText={setPlace}
              placeholder="місто / країна"
              placeholderTextColor={colors.muted}
            />
          </View>
        </View>

        <Text style={styles.label}>Теми / жанри</Text>
        <Text style={styles.hint}>Список зростає разом із темами в каталозі книг.</Text>
        <ThemeBoxes selected={themes} onToggle={(theme) => toggleTheme(theme, themes, setThemes)} />

        <Text style={styles.label}>Оберіть аватар</Text>
        {avatarUri ? (
          <View style={styles.currentAvatarRow}>
            <Text style={styles.hint}>Поточний:</Text>
            <AvatarImg uri={avatarUri} style={styles.avatarSm} />
          </View>
        ) : null}
        {avatars.length === 0 ? (
          <Text style={styles.hint}>
            Колекція аватарів порожня — запустіть sync_avatar_collection на сервері.
          </Text>
        ) : (
          <View style={styles.avatarPick}>
            {avatars.map((a) => {
              const on = avatarChoice === a.id;
              return (
                <Pressable
                  key={a.id}
                  style={[styles.avatarPickItem, on ? styles.avatarPickItemOn : null]}
                  onPress={() => setAvatarChoice(a.id)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: on }}
                  accessibilityLabel={a.name}
                >
                  <AvatarImg uri={a.image_url} style={styles.avatarPickImg} />
                </Pressable>
              );
            })}
          </View>
        )}

        <View style={styles.actions}>
          <ShelfLogoChip
            title="Зберегти профіль"
            icon="check"
            style={styles.actionChip}
            onPress={saveProfile}
          />
          <ShelfLogoChip
            title="Скасувати"
            icon="close"
            style={styles.actionChip}
            onPress={() => {
              setEditing(false);
              setAvatarChoice(null);
            }}
          />
        </View>

        <Text style={styles.sectionTitle}>Підпрофілі</Text>
        <Text style={styles.hint}>
          До {MAX_SUBPROFILES} шт. Стрічка = книги для вас або будь-якого підпрофілю.
        </Text>
        {subprofiles.map((sp) => (
          <View key={sp.id} style={styles.subCard}>
            <View style={styles.subMain}>
              <Text style={styles.subName}>{sp.name}</Text>
              <Text style={styles.metaLeft}>
                {sp.birthday ? `${formatBday(sp.birthday)}` : ""}
                {sp.age != null ? `${sp.birthday ? " · " : ""}${sp.age} р.` : sp.birthday ? "" : "—"}
                {sp.place ? ` · ${sp.place}` : ""}
              </Text>
              <Text style={styles.metaLeft}>
                {(sp.preferred_subjects || []).length
                  ? sp.preferred_subjects.join(", ")
                  : "Теми не обрано"}
              </Text>
            </View>
            <View style={styles.subActions}>
              <ShelfLogoChip
                title="Редагувати"
                icon="edit"
                style={styles.subChip}
                onPress={() => editSubDraft(sp)}
              />
              <ShelfLogoChip
                title="Видалити"
                icon="trash"
                danger
                style={styles.subChip}
                onPress={() => deleteSubprofile(sp)}
              />
            </View>
          </View>
        ))}
        {canAddSub ? (
          <ShelfLogoChip
            title="+ Додати підпрофіль"
            icon="add"
            style={styles.chipStretch}
            onPress={emptySubDraft}
          />
        ) : (
          <Text style={styles.hint}>Досягнуто ліміт підпрофілів.</Text>
        )}
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.screen }}
      contentContainerStyle={{ padding: 20 }}
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.headerRow}>
        <Text style={styles.pageTitle}>Профіль</Text>
        <View style={styles.headerActions}>
          <ShelfLogoChip title="Редагувати" icon="edit" style={styles.headerChip} onPress={startEdit} />
          {canAddSub ? (
            <ShelfLogoChip
              title="+ Підпрофіль"
              icon="add"
              style={styles.headerChip}
              onPress={emptySubDraft}
            />
          ) : null}
        </View>
      </View>

      <View style={styles.identity}>
        {avatarUri ? (
          <AvatarImg uri={avatarUri} style={styles.avatar} />
        ) : (
          <View style={[styles.avatar, styles.avatarEmpty]}>
            <Text style={styles.avatarLetter}>
              {(user?.username || "?").slice(0, 1).toUpperCase()}
            </Text>
          </View>
        )}
        <View style={styles.identityText}>
          <Text style={styles.fieldLine}>
            <Text style={styles.fieldKey}>Ім'я: </Text>
            {user?.username || "—"}
          </Text>
          <Text style={styles.fieldLine}>
            <Text style={styles.fieldKey}>Про себе: </Text>
            {user?.biography || "—"}
          </Text>
          <Text style={styles.fieldLine}>
            <Text style={styles.fieldKey}>Дата народження: </Text>
            {user?.birthday ? formatBday(user.birthday) : "—"}
          </Text>
          <Text style={styles.fieldLine}>
            <Text style={styles.fieldKey}>Вік: </Text>
            {user?.age != null ? `${user.age} р.` : "—"}
          </Text>
          <Text style={styles.fieldLine}>
            <Text style={styles.fieldKey}>Місце проживання: </Text>
            {user?.place || "—"}
          </Text>
          <Pressable onPress={startEdit}>
            <Text style={styles.editLink}>
              Змінити логін, біографію, дату народження, місце, теми, аватар →
            </Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitleInline}>Теми / жанри</Text>
        <ShelfLogoChip title="Обрати теми" icon="tags" style={styles.headerChip} onPress={startEdit} />
      </View>
      {(user?.preferred_subjects || []).length > 0 ? (
        <View style={styles.badgeRow}>
          {(user?.preferred_subjects || []).map((t) => (
            <View key={t} style={styles.badge}>
              <Text style={styles.badgeText}>{t}</Text>
            </View>
          ))}
        </View>
      ) : (
        <Text style={styles.hint}>
          Не обрано — стрічка без обмеження тем для основного профілю.{" "}
          <Text style={styles.linkInline} onPress={startEdit}>
            Обрати
          </Text>
        </Text>
      )}

      <View style={styles.sectionHead}>
        <Text style={styles.sectionTitleInline}>Підпрофілі</Text>
        {canAddSub ? (
          <ShelfLogoChip
            title="+ Додати"
            icon="add"
            style={styles.headerChip}
            onPress={emptySubDraft}
          />
        ) : null}
      </View>
      <Text style={styles.hint}>
        Для пошуку книг іншій людині. Стрічка = пости під ваш профіль або будь-який підпрофіль.
      </Text>
      {subprofiles.length === 0 ? (
        <Text style={styles.hint}>
          Немає підпрофілів.
          {canAddSub ? (
            <Text style={styles.linkInline} onPress={emptySubDraft}>
              {" "}
              Створити
            </Text>
          ) : null}
        </Text>
      ) : (
        subprofiles.map((sp) => (
          <View key={sp.id} style={styles.subCard}>
            <View style={styles.subMain}>
              <Text style={styles.subName}>{sp.name}</Text>
              <Text style={styles.metaLeft}>
                {sp.birthday ? formatBday(sp.birthday) : ""}
                {sp.age != null ? `${sp.birthday ? " · " : ""}${sp.age} р.` : ""}
                {sp.place
                  ? `${sp.birthday || sp.age != null ? " · " : ""}${sp.place}`
                  : ""}
              </Text>
              <Text style={styles.metaLeft}>
                {(sp.preferred_subjects || []).length
                  ? sp.preferred_subjects.join(", ")
                  : "Теми не обрано"}
              </Text>
            </View>
            <View style={styles.subActions}>
              <ShelfLogoChip
                title="Редагувати"
                icon="edit"
                style={styles.subChip}
                onPress={() => editSubDraft(sp)}
              />
              <ShelfLogoChip
                title="Видалити"
                icon="trash"
                danger
                style={styles.subChip}
                onPress={() => deleteSubprofile(sp)}
              />
            </View>
          </View>
        ))
      )}
      {!canAddSub && subprofiles.length > 0 ? (
        <Text style={styles.hint}>Досягнуто ліміт підпрофілів ({MAX_SUBPROFILES}).</Text>
      ) : null}

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
      <View style={styles.actions}>
        <ShelfLogoChip title="Зберегти URL" icon="cloud" style={styles.actionChip} onPress={saveApi} />
        <ShelfLogoChip title="Вийти" icon="trash" danger style={styles.actionChip} onPress={logout} />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  pageTitle: {
    fontSize: fs(22),
    fontWeight: "800",
    color: colors.ink,
    marginBottom: s(4),
  },
  headerRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    justifyContent: "space-between",
    gap: s(10),
    marginBottom: s(16),
  },
  headerActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: s(8),
    flexShrink: 1,
  },
  headerChip: { flexGrow: 0 },
  identity: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: s(14),
    marginBottom: s(20),
  },
  identityText: { flex: 1, minWidth: 0 },
  avatar: {
    width: s(96),
    height: s(96),
    borderRadius: s(48),
    backgroundColor: colors.paperDark,
    borderWidth: 1,
    borderColor: colors.line,
  },
  avatarEmpty: { alignItems: "center", justifyContent: "center" },
  avatarLetter: { fontSize: fs(32), color: colors.ink, fontWeight: "800" },
  avatarSm: {
    width: s(48),
    height: s(48),
    borderRadius: s(24),
    backgroundColor: colors.paperDark,
    borderWidth: 1,
    borderColor: colors.line,
  },
  fieldLine: {
    color: colors.ink,
    fontSize: fs(14),
    lineHeight: fs(20),
    marginBottom: 4,
  },
  fieldKey: { fontWeight: "800" },
  editLink: {
    color: colors.stamp,
    fontSize: fs(12),
    fontWeight: "700",
    marginTop: s(6),
  },
  sectionHead: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    justifyContent: "space-between",
    gap: s(8),
    marginTop: s(8),
    marginBottom: s(6),
  },
  sectionTitle: {
    marginTop: s(22),
    marginBottom: 4,
    fontSize: fs(17),
    fontWeight: "800",
    color: colors.ink,
  },
  sectionTitleInline: {
    fontSize: fs(17),
    fontWeight: "800",
    color: colors.ink,
  },
  badgeRow: { flexDirection: "row", flexWrap: "wrap", gap: s(8), marginBottom: s(8) },
  badge: {
    backgroundColor: colors.ink,
    borderRadius: btnRadius,
    paddingHorizontal: s(10),
    paddingVertical: s(5),
  },
  badgeText: { color: colors.white, fontSize: fs(12), fontWeight: "600" },
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
  label: { marginTop: s(14), color: colors.muted, fontSize: fs(12), fontWeight: "600" },
  hint: { color: colors.muted, fontSize: fs(12), marginTop: 4, lineHeight: fs(16) },
  linkInline: { color: colors.stamp, fontWeight: "700" },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: s(12),
    fontSize: fs(16),
    minHeight: s(48),
  },
  bioInput: { minHeight: s(88), textAlignVertical: "top" },
  row2: { flexDirection: "row", gap: s(12), alignItems: "flex-start" },
  colAge: { width: "42%", flexShrink: 0 },
  colPlace: { flex: 1, minWidth: 0 },
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: s(10),
    marginTop: s(18),
  },
  actionChip: { flexGrow: 1, flexBasis: "40%" },
  chipStretch: { marginTop: s(12), alignSelf: "stretch" },
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
  currentAvatarRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: s(10),
    marginTop: s(8),
  },
  avatarPick: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: s(10),
    marginTop: s(10),
  },
  avatarPickItem: {
    borderRadius: s(40),
    borderWidth: 3,
    borderColor: "transparent",
    padding: 2,
  },
  avatarPickItemOn: {
    borderColor: colors.ink,
  },
  avatarPickImg: {
    width: s(72),
    height: s(72),
    borderRadius: s(36),
    backgroundColor: colors.paperDark,
  },
  subCard: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    paddingVertical: s(12),
    gap: s(10),
  },
  subMain: { flex: 1, minWidth: 0 },
  subName: { color: colors.ink, fontWeight: "700", fontSize: fs(15) },
  metaLeft: { color: colors.muted, fontSize: fs(13), marginTop: 2 },
  subActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: s(8),
  },
  subChip: { flexGrow: 1, flexBasis: "40%" },
});
