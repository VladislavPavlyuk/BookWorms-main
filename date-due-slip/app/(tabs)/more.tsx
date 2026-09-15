import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { useAuth } from "../../src/auth";
import { getApiBase, setApiBase } from "../../src/api";
import { colors } from "../../src/theme";

export default function More() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [api, setApi] = useState("");

  useEffect(() => {
    getApiBase().then(setApi);
  }, []);

  const saveApi = async () => {
    await setApiBase(api.trim());
    Alert.alert("API", "Збережено. Перелогінься якщо токен від іншого хоста.");
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.name}>{user?.username}</Text>
      <Text style={styles.bio}>{user?.biography || "немає біографії"}</Text>

      <Pressable style={styles.row} onPress={() => router.push("/exchanges")}>
        <Text style={styles.rowText}>Обміни / позики</Text>
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
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.paper, padding: 20 },
  name: { fontSize: 22, fontWeight: "800", color: colors.ink },
  bio: { color: colors.muted, marginBottom: 24, marginTop: 4 },
  row: { borderBottomWidth: 1, borderColor: colors.line, paddingVertical: 14 },
  rowText: { color: colors.ink, fontSize: 16, fontWeight: "600" },
  label: { marginTop: 28, color: colors.muted, fontSize: 12 },
  input: { borderBottomWidth: 1, borderColor: colors.line, color: colors.ink, paddingVertical: 8 },
  btn: { backgroundColor: colors.ink, padding: 12, marginTop: 12 },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700" },
});
