import { useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
} from "react-native";
import { Link } from "expo-router";
import { useAuth } from "../../src/auth";
import { ApiError } from "../../src/api";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { PasswordField } from "../../src/PasswordField";
import { colors, fs, s, btnRadius } from "../../src/theme";

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
      <CyrillicTextInput
        placeholder="Логін"
        placeholderTextColor={colors.muted}
        autoCapitalize="none"
        keyboardType="default"
        textContentType="username"
        style={styles.input}
        value={username}
        onChangeText={setUsername}
      />
      <PasswordField
        placeholder="Пароль"
        placeholderTextColor={colors.muted}
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
  wrap: { flex: 1, backgroundColor: colors.screen, padding: s(28), justifyContent: "center" },
  stamp: {
    color: colors.stamp,
    fontSize: fs(28),
    fontWeight: "800",
    letterSpacing: 2,
    textAlign: "center",
  },
  sub: {
    color: colors.muted,
    textAlign: "center",
    marginBottom: s(28),
    marginTop: s(6),
    fontSize: fs(16),
  },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: s(12),
    marginBottom: s(16),
    fontSize: fs(16),
    minHeight: s(48),
  },
  btn: { backgroundColor: colors.ink, padding: s(14), marginTop: s(8), minHeight: s(54), borderRadius: btnRadius },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700", fontSize: fs(18) },
  link: { color: colors.stamp, textAlign: "center", marginTop: s(18), fontSize: fs(16) },
});
