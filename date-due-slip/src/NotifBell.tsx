import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "./theme";
import { useUnread } from "./unread";

/**
 * Дзвіночок у headerRight.
 * Бейдж лише всередині hitbox — на Pixel/Android header кліпає overflow,
 * тому absolute з top/right < 0 робить кружок невидимим (на емуляторі інколи «проскакує»).
 */
export function NotifBell() {
  const router = useRouter();
  const { unread } = useUnread();
  const label = unread > 99 ? "99+" : String(unread);

  return (
    <Pressable
      onPress={() => router.push("/notifications")}
      hitSlop={8}
      style={styles.wrap}
      accessibilityRole="button"
      accessibilityLabel={
        unread > 0 ? `Сповіщення, непрочитаних ${unread}` : "Сповіщення"
      }
    >
      <Ionicons name="notifications" size={22} color={colors.ink} />
      {unread > 0 ? (
        <View style={styles.badge} pointerEvents="none">
          <Text style={styles.badgeText}>{label}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginRight: 8,
    minWidth: 44,
    height: 40,
    paddingHorizontal: 6,
    alignItems: "center",
    justifyContent: "center",
    overflow: "visible",
  },
  badge: {
    position: "absolute",
    top: 2,
    right: 2,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: "#E53935",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
    borderWidth: 1.5,
    borderColor: colors.paperDark,
    zIndex: 2,
    elevation: 3,
  },
  badgeText: {
    color: "#fff",
    fontSize: 10,
    fontWeight: "800",
    lineHeight: 12,
    includeFontPadding: false,
  },
});
