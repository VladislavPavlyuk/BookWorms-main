import { Tabs, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { Platform } from "react-native";
import { HeaderActions } from "../../src/BurgerMenu";
import { colors } from "../../src/theme";
import { useUnread } from "../../src/unread";

export default function TabsLayout() {
  const { refresh } = useUnread();

  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh])
  );

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.paperDark },
        headerTintColor: colors.ink,
        headerTitleStyle: { fontWeight: "700", letterSpacing: 1 },
        headerRightContainerStyle: {
          paddingRight: Platform.OS === "android" ? 8 : 4,
          overflow: "visible",
        },
        headerRight: () => <HeaderActions />,
        sceneContainerStyle: { backgroundColor: "transparent" },
        // Nav moved to burger menu (top-right)
        tabBarStyle: { display: "none", height: 0 },
        tabBarShowLabel: false,
      }}
    >
      <Tabs.Screen name="index" options={{ title: "", headerShown: false }} />
      <Tabs.Screen name="shelf" options={{ title: "" }} />
      <Tabs.Screen name="slips" options={{ title: "" }} />
      <Tabs.Screen name="browse" options={{ title: "" }} />
      <Tabs.Screen name="more" options={{ title: "" }} />
    </Tabs>
  );
}
