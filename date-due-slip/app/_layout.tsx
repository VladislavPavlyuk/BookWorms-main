import "react-native-gesture-handler";
import { useEffect, type ReactNode } from "react";
import { ActivityIndicator, View } from "react-native";
import { Stack, useRouter, useSegments } from "expo-router";
import { AuthProvider, useAuth } from "../src/auth";
import { FeedSearchProvider } from "../src/feedSearch";
import { SiteHeader } from "../src/SiteHeader";
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

function AppChrome({ children }: { children: ReactNode }) {
  const segments = useSegments();
  const inAuth = segments[0] === "(auth)";
  if (inAuth) return <>{children}</>;
  return (
    <View style={{ flex: 1 }}>
      <SiteHeader />
      <View style={{ flex: 1 }}>{children}</View>
    </View>
  );
}

export default function Root() {
  return (
    <SiteBackground>
      <AuthProvider>
        <UnreadProvider>
          <FeedSearchProvider>
            <Gate>
              <AppChrome>
                <Stack
                  screenOptions={{
                    headerShown: false,
                    contentStyle: { backgroundColor: "transparent" },
                  }}
                >
                  <Stack.Screen name="(tabs)" />
                  <Stack.Screen name="(auth)" />
                  <Stack.Screen name="exchanges" />
                  <Stack.Screen name="notifications" />
                  <Stack.Screen name="chat/[id]" />
                  <Stack.Screen name="post/new" />
                  <Stack.Screen name="post/[id]" />
                  <Stack.Screen name="book/[id]" />
                  <Stack.Screen name="copy/[id]" />
                  <Stack.Screen name="user/[id]" />
                </Stack>
              </AppChrome>
            </Gate>
          </FeedSearchProvider>
        </UnreadProvider>
      </AuthProvider>
    </SiteBackground>
  );
}
