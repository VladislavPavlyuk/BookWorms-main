import { Tabs, useFocusEffect } from "expo-router";
import { useCallback } from "react";
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
        headerShown: false,
        tabBarStyle: { display: "none", height: 0 },
        tabBarShowLabel: false,
      }}
    >
      <Tabs.Screen name="index" options={{ title: "" }} />
      <Tabs.Screen name="shelf" options={{ title: "" }} />
      <Tabs.Screen name="slips" options={{ title: "" }} />
      <Tabs.Screen name="browse" options={{ title: "" }} />
      <Tabs.Screen name="more" options={{ title: "" }} />
    </Tabs>
  );
}
