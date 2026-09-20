import "react-native-gesture-handler";
import { useEffect, type ReactNode } from "react";
import { ActivityIndicator, View } from "react-native";
import { Stack, useRouter, useSegments } from "expo-router";
import { AuthProvider, useAuth } from "../src/auth";
import { HeaderActions } from "../src/BurgerMenu";
import { SiteBackground } from "../src/SiteBackground";
import { UnreadProvider } from "../src/unread";
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
      <View style={{ flex: 1, justifyContent: "center" }}>
        <ActivityIndicator color={colors.stamp} />
      </View>
    );
  }
  return <>{children}</>;
}

export default function Root() {
  return (
    <SiteBackground>
      <AuthProvider>
        <UnreadProvider>
          <Gate>
            <Stack
              screenOptions={{
                headerShown: false,
                contentStyle: { backgroundColor: "transparent" },
                headerStyle: { backgroundColor: colors.paperDark },
                headerTintColor: colors.ink,
              }}
            >
              <Stack.Screen name="(tabs)" />
              <Stack.Screen name="(auth)" />
              <Stack.Screen
                name="exchanges"
                options={{ headerShown: true, title: "Запити на обмін", headerRight: () => <HeaderActions /> }}
              />
              <Stack.Screen name="notifications" options={{ headerShown: true, title: "Сповіщення", headerRight: () => <HeaderActions /> }} />
              <Stack.Screen
                name="chat/[id]"
                options={{ headerShown: true, title: "Чат", headerRight: () => <HeaderActions /> }}
              />
              <Stack.Screen
                name="post/new"
                options={{ headerShown: true, title: "Новий пост", headerRight: () => <HeaderActions /> }}
              />
              <Stack.Screen
                name="post/[id]"
                options={{ headerShown: true, title: "Пост", headerRight: () => <HeaderActions /> }}
              />
              <Stack.Screen
                name="book/[id]"
                options={{ headerShown: true, title: "Книга", headerRight: () => <HeaderActions /> }}
              />
              <Stack.Screen
                name="user/[id]"
                options={{ headerShown: true, title: "Полиця", headerRight: () => <HeaderActions /> }}
              />
            </Stack>
          </Gate>
        </UnreadProvider>
      </AuthProvider>
    </SiteBackground>
  );
}
