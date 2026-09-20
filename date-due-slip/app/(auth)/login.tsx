import { useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Link } from "expo-router";
import { useAuth } from "../../src/auth";
import { ApiError } from "../../src/api";
import { colors } from "../../src/theme";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (e) {
      Alert.alert("Вхід", e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.wrap}
    >
      <Text style={styles.stamp}>РЕЧЕНЕЦЬ</Text>
      <Text style={styles.sub}>локальна мережа</Text>
      <TextInput
        placeholder="Логін"
        placeholderTextColor={colors.muted}
        autoCapitalize="none"
        style={styles.input}
        value={username}
        onChangeText={setUsername}
      />
      <TextInput
        placeholder="Пароль"
        placeholderTextColor={colors.muted}
        secureTextEntry
        style={styles.input}
        value={password}
        onChangeText={setPassword}
      />
      <Pressable style={styles.btn} onPress={onSubmit} disabled={busy}>
        <Text style={styles.btnText}>{busy ? "…" : "Увійти"}</Text>
      </Pressable>
      <Link href="/(auth)/register" style={styles.link}>
        Реєстрація
      </Link>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.screen, padding: 28, justifyContent: "center" },
  stamp: {
    color: colors.stamp,
    fontSize: 28,
    fontWeight: "800",
    letterSpacing: 2,
    textAlign: "center",
  },
  sub: { color: colors.muted, textAlign: "center", marginBottom: 28, marginTop: 6 },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: 10,
    marginBottom: 16,
    fontSize: 16,
  },
  btn: { backgroundColor: colors.ink, padding: 14, marginTop: 8 },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700" },
  link: { color: colors.stamp, textAlign: "center", marginTop: 18 },
});
