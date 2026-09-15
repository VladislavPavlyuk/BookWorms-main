import { Tabs } from "expo-router";
import { colors } from "../../src/theme";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.paperDark },
        headerTintColor: colors.ink,
        headerTitleStyle: { fontWeight: "700", letterSpacing: 1 },
        tabBarStyle: { backgroundColor: colors.paperDark, borderTopColor: colors.line },
        tabBarActiveTintColor: colors.stamp,
        tabBarInactiveTintColor: colors.muted,
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Стрічка", tabBarLabel: "Стрічка" }} />
      <Tabs.Screen name="shelf" options={{ title: "Полиця", tabBarLabel: "Полиця" }} />
      <Tabs.Screen name="slips" options={{ title: "Date Due Slip", tabBarLabel: "Терміни" }} />
      <Tabs.Screen name="browse" options={{ title: "Чужі полиці", tabBarLabel: "Каталог" }} />
      <Tabs.Screen name="more" options={{ title: "Ще", tabBarLabel: "Ще" }} />
    </Tabs>
  );
}
