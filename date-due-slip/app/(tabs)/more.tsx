import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { useAuth } from "../../src/auth";
import { ApiError, AuthApi, getApiBase, setApiBase } from "../../src/api";
import { colors } from "../../src/theme";

export default function More() {
  const { user, logout, reload } = useAuth();
  const router = useRouter();
  const [api, setApi] = useState("");
  const [username, setUsername] = useState(user?.username || "");
  const [biography, setBiography] = useState(user?.biography || "");
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    getApiBase().then(setApi);
  }, []);

  useEffect(() => {
    setUsername(user?.username || "");
    setBiography(user?.biography || "");
  }, [user]);

  const saveApi = async () => {
    await setApiBase(api.trim());
    Alert.alert("API", "Збережено. Перелогінься якщо токен від іншого хоста.");
  };

  const saveProfile = async () => {
    try {
      await AuthApi.updateMe({ username: username.trim(), biography });
      await reload();
      setEditing(false);
      Alert.alert("Профіль", "Збережено.");
    } catch (e) {
      Alert.alert("Профіль", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.paper }} contentContainerStyle={{ padding: 20 }}>
      {editing ? (
        <>
          <Text style={styles.label}>Логін</Text>
          <TextInput style={styles.input} value={username} onChangeText={setUsername} autoCapitalize="none" />
          <Text style={styles.label}>Біографія</Text>
          <TextInput style={styles.input} value={biography} onChangeText={setBiography} multiline />
          <Pressable style={styles.btn} onPress={saveProfile}>
            <Text style={styles.btnText}>Зберегти профіль</Text>
          </Pressable>
          <Pressable onPress={() => setEditing(false)}>
            <Text style={styles.cancel}>Скасувати</Text>
          </Pressable>
        </>
      ) : (
        <>
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
      <Pressable style={styles.row} onPress={() => router.push("/exchanges")}>
        <Text style={styles.rowText}>Обміни / позики / чати</Text>
      </Pressable>
      <Pressable style={styles.row} onPress={() => router.push("/post/new")}>
        <Text style={styles.rowText}>Новий пост</Text>
      </Pressable>

      <Text style={styles.label}>API (NAS)</Text>
      <TextInput style={styles.input} value={api} onChangeText={setApi} autoCapitalize="none" />
      <Pressable style={styles.btn} onPress={saveApi}>
        <Text style={styles.btnText}>Зберегти URL</Text>
      </Pressable>
      <Pressable style={[styles.btn, { backgroundColor: colors.stamp, marginTop: 24 }]} onPress={logout}>
        <Text style={styles.btnText}>Вийти</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  name: { fontSize: 22, fontWeight: "800", color: colors.ink },
  bio: { color: colors.muted, marginTop: 4 },
  email: { color: colors.muted, fontSize: 12, marginBottom: 16, marginTop: 2 },
  row: { borderBottomWidth: 1, borderColor: colors.line, paddingVertical: 14 },
  rowText: { color: colors.ink, fontSize: 16, fontWeight: "600" },
  label: { marginTop: 20, color: colors.muted, fontSize: 12 },
  input: { borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, paddingVertical: 8 },
  btn: { backgroundColor: colors.ink, padding: 12, marginTop: 12 },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700" },
  cancel: { color: colors.muted, textAlign: "center", marginTop: 12, fontWeight: "700" },
});
