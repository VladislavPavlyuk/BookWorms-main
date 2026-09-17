import "react-native-gesture-handler";
import { useEffect, type ReactNode } from "react";
import { ActivityIndicator, View } from "react-native";
import { Stack, useRouter, useSegments } from "expo-router";
import { AuthProvider, useAuth } from "../src/auth";
import { colors } from "../src/theme";

function Gate({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    const inAuth = segments[0] === "(auth)";
    if (!user && !inAuth) router.replace("/(auth)/login");
    if (user && inAuth) router.replace("/(tabs)");
  }, [user, ready, segments]);

  if (!ready) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.paper, justifyContent: "center" }}>
        <ActivityIndicator color={colors.stamp} />
      </View>
    );
  }
  return <>{children}</>;
}

export default function Root() {
  return (
    <AuthProvider>
      <Gate>
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.paper } }}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="(auth)" />
          <Stack.Screen name="exchanges" options={{ headerShown: true, title: "Обміни" }} />
          <Stack.Screen name="notifications" options={{ headerShown: true, title: "Сповіщення" }} />
          <Stack.Screen name="chat/[id]" options={{ headerShown: true, title: "Чат" }} />
          <Stack.Screen name="post/new" options={{ headerShown: true, title: "Новий пост" }} />
          <Stack.Screen name="post/[id]" options={{ headerShown: true, title: "Пост" }} />
          <Stack.Screen name="book/[id]" options={{ headerShown: true, title: "Книга" }} />
          <Stack.Screen name="user/[id]" options={{ headerShown: true, title: "Полиця" }} />
        </Stack>
      </Gate>
    </AuthProvider>
  );
}
