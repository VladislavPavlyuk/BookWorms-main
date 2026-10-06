import { useEffect, useRef, useState } from "react";
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
  View,
} from "react-native";
import { Link, useRouter } from "expo-router";
import { AuthApi, setTokens } from "../../src/api";
import { useAuth } from "../../src/auth";
import { ApiError } from "../../src/api";
import { PasswordField } from "../../src/PasswordField";
import { CyrillicTextInput } from "../../src/CyrillicTextInput";
import { colors, fs, s, btnRadius } from "../../src/theme";

export default function Register() {
  const router = useRouter();
  const { reload } = useAuth();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [biography, setBiography] = useState("");
  const [busy, setBusy] = useState(false);
  const [userStatus, setUserStatus] = useState("");
  const [emailStatus, setEmailStatus] = useState("");
  const [userOk, setUserOk] = useState<boolean | null>(null);
  const [emailOk, setEmailOk] = useState<boolean | null>(null);
  const [userTaken, setUserTaken] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [confirmed, setConfirmed] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    const u = username.trim();
    const e = email.trim();
    if (!u && !e) {
      setUserStatus("");
      setEmailStatus("");
      setUserOk(null);
      setEmailOk(null);
      setUserTaken(false);
      setSuggestions([]);
      return;
    }
    if (u) setUserStatus("Перевірка…");
    if (e) setEmailStatus("Перевірка…");
    timer.current = setTimeout(async () => {
      try {
        const data = await AuthApi.checkAvailability(u, e);
        if (u) {
          if (data.username_taken) {
            if (confirmed && confirmed === u) {
              setUserTaken(false);
              setUserOk(true);
              setUserStatus(`Підтверджено: ${u}`);
              setSuggestions([]);
            } else {
              setUserTaken(true);
              setUserOk(false);
              setUserStatus("Логін уже зайнятий.");
              setSuggestions(!data.email_taken ? data.suggestions || [] : []);
            }
          } else if (data.username_available) {
            setUserTaken(false);
            setUserOk(true);
            setUserStatus("Логін вільний.");
            setSuggestions([]);
            setConfirmed(u);
          } else {
            setUserStatus("");
            setSuggestions([]);
          }
        } else {
          setUserStatus("");
          setUserOk(null);
          setUserTaken(false);
          setSuggestions([]);
        }
        if (e) {
          if (data.email_taken) {
            setEmailOk(false);
            setEmailStatus("Email уже використовується.");
            setSuggestions([]);
          } else if (data.email_available) {
            setEmailOk(true);
            setEmailStatus("Email вільний.");
            if (data.username_taken && confirmed !== u) {
              setSuggestions(data.suggestions || []);
            }
          } else {
            setEmailStatus("");
            setEmailOk(null);
          }
        } else {
          setEmailStatus("");
          setEmailOk(null);
        }
      } catch {
        setUserStatus("");
        setEmailStatus("");
      }
    }, 400);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [username, email, confirmed]);

  const pickSuggestion = (name: string) => {
    setUsername(name);
    setConfirmed(name);
    setUserTaken(false);
    setUserOk(true);
    setUserStatus(`Підтверджено: ${name}`);
    setSuggestions([]);
  };

  const canSubmit =
    !!username.trim() &&
    !!email.trim() &&
    !!password &&
    emailOk !== false &&
    !(userTaken && confirmed !== username.trim());

  const onSubmit = async () => {
    if (!canSubmit) {
      Alert.alert(
        "Реєстрація",
        userTaken && confirmed !== username.trim()
          ? "Підтвердіть унікальний логін зі списку."
          : emailOk === false
            ? "Email уже використовується."
            : "Заповніть логін, email і пароль."
      );
      return;
    }
    setBusy(true);
    try {
      const data = await AuthApi.register(username.trim(), email.trim(), password, biography);
      if (data.access && data.refresh) {
        await setTokens(data.access, data.refresh);
        await reload();
        router.replace("/(tabs)");
        return;
      }

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
        <Text style={styles.title}>Реченець</Text>
        <Text style={styles.warn}>
          Підтвердіть email протягом 5 хвилин після реєстрації. Інакше акаунт буде
          автоматично видалено з бази — доведеться реєструватися знову.
        </Text>
        <CyrillicTextInput
          placeholder="Логін"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
          keyboardType="default"
          textContentType="username"
          style={styles.input}
          value={username}
          onChangeText={(t) => {
            setUsername(t);
            setConfirmed("");
          }}
        />
        {userStatus ? (
          <Text style={[styles.live, userOk === false && styles.liveBad, userOk && styles.liveOk]}>
            {userStatus}
          </Text>
        ) : null}
        {suggestions.length > 0 ? (
          <View style={styles.suggestBox}>
            <Text style={styles.suggestLabel}>Підтвердіть унікальний логін:</Text>
            <View style={styles.suggestRow}>
              {suggestions.map((name) => (
                <Pressable
                  key={name}
                  style={[styles.chip, confirmed === name && styles.chipOn]}
                  onPress={() => pickSuggestion(name)}
                >
                  <Text style={[styles.chipText, confirmed === name && styles.chipTextOn]}>
                    {name}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : null}
        <CyrillicTextInput
          placeholder="Email"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
          keyboardType="default"
          textContentType="emailAddress"
          style={styles.input}
          value={email}
          onChangeText={setEmail}
        />
        {emailStatus ? (
          <Text
            style={[styles.live, emailOk === false && styles.liveBad, emailOk && styles.liveOk]}
          >
            {emailStatus}
          </Text>
        ) : null}
        <PasswordField
          placeholder="Пароль (мін. 8)"
          placeholderTextColor={colors.muted}
          value={password}
          onChangeText={setPassword}
        />
        <CyrillicTextInput
          placeholder="Про себе"
          placeholderTextColor={colors.muted}
          style={styles.input}
          value={biography}
          onChangeText={setBiography}
          multiline
          autoCapitalize="sentences"
          keyboardType="default"
        />
        <Pressable
          style={[styles.btn, (!canSubmit || busy) && { opacity: 0.5 }]}
          onPress={onSubmit}
          disabled={busy || !canSubmit}
        >
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
  wrap: { padding: s(28), paddingTop: s(80) },
  title: { fontSize: fs(24), fontWeight: "800", color: colors.ink, marginBottom: s(12) },
  warn: {
    color: colors.danger,
    marginBottom: s(20),
    lineHeight: fs(22),
    fontWeight: "600",
    fontSize: fs(15),
  },
  input: {
    borderBottomWidth: 1,
    borderColor: colors.line,
    color: colors.ink,
    paddingVertical: s(12),
    marginBottom: s(8),
    fontSize: fs(16),
    minHeight: s(48),
  },
  live: { color: colors.muted, fontSize: fs(13), marginBottom: s(10) },
  liveOk: { color: colors.stampOk },
  liveBad: { color: colors.stamp },
  suggestBox: { marginBottom: s(12) },
  suggestLabel: { color: colors.muted, fontSize: fs(13), marginBottom: s(8) },
  suggestRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.paper,
    paddingVertical: s(8),
    paddingHorizontal: s(12),
    borderRadius: btnRadius,
  },
  chipOn: { backgroundColor: colors.stampOk, borderColor: colors.stampOk },
  chipText: { color: colors.ink, fontWeight: "700", fontSize: fs(13) },
  chipTextOn: { color: colors.white },
  btn: {
    backgroundColor: colors.stamp,
    padding: s(14),
    marginTop: s(8),
    minHeight: s(54),
    borderRadius: btnRadius,
  },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700", fontSize: fs(18) },
  link: { color: colors.muted, textAlign: "center", marginTop: s(18), fontSize: fs(16) },
});
