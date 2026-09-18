import { Tabs, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { Platform } from "react-native";
import { NotifBell } from "../../src/NotifBell";
import { colors } from "../../src/theme";
import { useUnread } from "../../src/unread";

export default function TabsLayout() {
  const { unread, refresh } = useUnread();
  const badge = unread > 0 ? (unread > 99 ? "99+" : unread) : undefined;

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
        // Pixel/Android кліпає badge, якщо вилазить за межі контейнера
        headerRightContainerStyle: {
          paddingRight: Platform.OS === "android" ? 12 : 8,
          overflow: "visible",
        },
        headerRight: () => <NotifBell />,
        tabBarStyle: { backgroundColor: colors.paperDark, borderTopColor: colors.line },
        tabBarActiveTintColor: colors.stamp,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Стрічка", tabBarLabel: "Стрічка" }} />
      <Tabs.Screen name="shelf" options={{ title: "Полиця", tabBarLabel: "Полиця" }} />
      <Tabs.Screen name="slips" options={{ title: "Date Due Slip", tabBarLabel: "Терміни" }} />
      <Tabs.Screen name="browse" options={{ title: "Чужі полиці", tabBarLabel: "Каталог" }} />
      <Tabs.Screen
        name="more"
        options={{
          title: "Ще",
          tabBarLabel: "Ще",
          tabBarBadge: badge,
          tabBarBadgeStyle: {
            backgroundColor: "#E53935",
            color: "#fff",
            fontSize: 11,
            fontWeight: "800",
          },
        }}
      />
    </Tabs>
  );
}
