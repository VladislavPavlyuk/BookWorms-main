import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "./theme";
import { useUnread } from "./unread";

type Props = {
  /** ink = solid header chip (matches Search / burger); plain = icon only */
  variant?: "ink" | "plain";
};

/**
 * Дзвіночок у headerRight.
 * Бейдж лише всередині hitbox — на Pixel/Android header кліпає overflow.
 */
export function NotifBell({ variant = "ink" }: Props) {
  const router = useRouter();
  const { unread } = useUnread();
  const label = unread > 99 ? "99+" : String(unread);
  const ink = variant === "ink";

  return (
    <Pressable
      onPress={() => router.push("/notifications")}
      hitSlop={4}
      style={({ pressed }) => [
        ink ? styles.ink : styles.plain,
        ink && pressed && styles.inkPressed,
      ]}
      accessibilityRole="button"
      accessibilityLabel={
        unread > 0 ? `Сповіщення, непрочитаних ${unread}` : "Сповіщення"
      }
    >
      <Ionicons name="notifications" size={22} color={ink ? colors.white : colors.ink} />
      {unread > 0 ? (
        <View style={[styles.badge, ink && styles.badgeOnInk]} pointerEvents="none">
          <Text style={styles.badgeText}>{label}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  ink: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
    borderWidth: 1,
    borderColor: colors.ink,
    marginLeft: 6,
  },
  inkPressed: {
    backgroundColor: "#1a140e",
  },
  plain: {
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
  badgeOnInk: {
    borderColor: colors.ink,
  },
  badgeText: {
    color: "#fff",
    fontSize: 10,
    fontWeight: "800",
    lineHeight: 12,
    includeFontPadding: false,
  },
});
