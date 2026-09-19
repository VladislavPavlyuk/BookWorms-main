import { useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TextInput,
} from "react-native";
import { Link, useRouter } from "expo-router";
import { AuthApi, setTokens } from "../../src/api";
import { useAuth } from "../../src/auth";
import { ApiError } from "../../src/api";
import { colors } from "../../src/theme";

export default function Register() {
  const router = useRouter();
  const { reload } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [biography, setBiography] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async () => {
    setBusy(true);
    try {
      const data = await AuthApi.register(username.trim(), email.trim(), password, biography);
      if (data.access && data.refresh) {
        await setTokens(data.access, data.refresh);
        await reload();
        router.replace("/(tabs)");
        return;
      }

      // Free Web3Forms блокує RN fetch як server-side — лише системний браузер.
      if (data.web3forms_browser_url) {
        try {
          await Linking.openURL(data.web3forms_browser_url);
        } catch {
          /* ignore */
        }
      }

      const lines = [
        data.detail || "Акаунт створено.",
        data.web3forms_browser_url
          ? "\n\nВідкрито браузер для відправки листа Web3Forms."
          : "\n\nНемає bridge-URL — онови api на NAS.",
        data.activation_url ? `\n\nЛінк активації:\n${data.activation_url}` : "",
        data.activation_timeout_minutes
          ? `\n\nМаєш ${data.activation_timeout_minutes} хв.`
          : "\n\nМаєш 5 хв.",
      ];

      const buttons: {
        text: string;
        onPress?: () => void;
      }[] = [{ text: "OK", onPress: () => router.replace("/(auth)/login") }];

      if (data.web3forms_browser_url) {
        buttons.unshift({
          text: "Надіслати лист",
          onPress: () => {
            Linking.openURL(data.web3forms_browser_url!);
            router.replace("/(auth)/login");
          },
        });
      }
      if (data.activation_url) {
        buttons.unshift({
          text: "Відкрити лінк",
          onPress: () => {
            Linking.openURL(data.activation_url!);
            router.replace("/(auth)/login");
          },
        });
        buttons.unshift({
          text: "Поділитись лінком",
          onPress: () => {
            Share.share({ message: data.activation_url!, url: data.activation_url });
            router.replace("/(auth)/login");
          },
        });
      }

      Alert.alert("Реєстрація", lines.join(""), buttons);
    } catch (e) {
      Alert.alert("Реєстрація", e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={{ flex: 1, backgroundColor: colors.screen }}
    >
      <ScrollView contentContainerStyle={styles.wrap}>
        <Text style={styles.title}>Новий квиток</Text>
        <Text style={styles.warn}>
          Підтвердіть email протягом 5 хвилин після реєстрації. Інакше акаунт буде
          автоматично видалено з бази — доведеться реєструватися знову.
        </Text>
        <TextInput
          placeholder="Логін"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
          style={styles.input}
          value={username}
          onChangeText={setUsername}
        />
        <TextInput
          placeholder="Email"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
          keyboardType="email-address"
          style={styles.input}
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          placeholder="Пароль (мін. 8)"
          placeholderTextColor={colors.muted}
          secureTextEntry
          style={styles.input}
          value={password}
          onChangeText={setPassword}
        />
        <TextInput
          placeholder="Біографія"
          placeholderTextColor={colors.muted}
          style={styles.input}
          value={biography}
          onChangeText={setBiography}
        />
        <Pressable style={styles.btn} onPress={onSubmit} disabled={busy}>
          <Text style={styles.btnText}>{busy ? "…" : "Зареєструватись"}</Text>
        </Pressable>
        <Link href="/(auth)/login" style={styles.link}>
          Вже є акаунт
        </Link>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: 28, paddingTop: 80 },
  title: { fontSize: 24, fontWeight: "800", color: colors.ink, marginBottom: 12 },
  warn: {
    color: colors.danger,
    marginBottom: 20,
    lineHeight: 20,
    fontWeight: "600",
  },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: 10,
    marginBottom: 16,
    fontSize: 16,
  },
  btn: { backgroundColor: colors.stamp, padding: 14, marginTop: 8 },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700" },
  link: { color: colors.muted, textAlign: "center", marginTop: 18 },
});
