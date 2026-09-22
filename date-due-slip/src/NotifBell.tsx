import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { BellGlyph } from "./HeaderGlyphs";
import { colors } from "./theme";
import { useUnread } from "./unread";

type Props = {
  /** paper = theme chrome (default); plain = icon only in stack headers */
  variant?: "paper" | "plain" | "ink";
};

/**
 * Дзвіночок у header — paper/line/ink як «Фільтр».
 * Glyph намальований View'ами (без Ionicons — на збірках шрифт інколи дає порожній квадрат).
 */
export function NotifBell({ variant = "paper" }: Props) {
  const router = useRouter();
  const { unread } = useUnread();
  const label = unread > 99 ? "99+" : String(unread);
  const chrome = variant === "paper" || variant === "ink";
  const solid = variant === "ink";
  const glyphColor = solid ? colors.white : colors.ink;

  return (
    <Pressable
      onPress={() => router.push("/notifications")}
      hitSlop={4}
      style={({ pressed }) => [
        chrome ? (solid ? styles.solid : styles.paper) : styles.plain,
        chrome && pressed && (solid ? styles.solidPressed : styles.paperPressed),
      ]}
      accessibilityRole="button"
      accessibilityLabel={
        unread > 0 ? `Сповіщення, непрочитаних ${unread}` : "Сповіщення"
      }
    >
      <BellGlyph color={glyphColor} size={20} />
      {unread > 0 ? (
        <View
          style={[styles.badge, solid && styles.badgeOnSolid]}
          pointerEvents="none"
        >
          <Text style={styles.badgeText}>{label}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  paper: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    marginLeft: 4,
  },
  paperPressed: {
    backgroundColor: colors.paperDark,
  },
  solid: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.ink,
    borderWidth: 1,
    borderColor: colors.ink,
    marginLeft: 4,
  },
  solidPressed: {
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
    top: 1,
    right: 1,
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: colors.stamp,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
    borderWidth: 1.5,
    borderColor: colors.white,
    zIndex: 2,
    elevation: 3,
  },
  badgeOnSolid: {
    borderColor: colors.ink,
  },
  badgeText: {
    color: colors.white,
    fontSize: 9,
    fontWeight: "800",
    lineHeight: 11,
    includeFontPadding: false,
  },
});
