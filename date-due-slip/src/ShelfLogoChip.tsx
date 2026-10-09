import {
  ImageBackground,
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { ShelfActionGlyph, type ShelfActionIcon } from "./ShelfActionGlyphs";
import { colors, fs, s } from "./theme";

type Props = {
  title: string;
  icon: ShelfActionIcon;
  onPress: () => void;
  /** Stamp outline (e.g. delete) instead of logo gradient. */
  danger?: boolean;
  accessibilityLabel?: string;
  style?: StyleProp<ViewStyle>;
};

/**
 * Compact chip — logo/FAB gradient + classic View glyph on the right.
 * Used for My Library toolbar (Вручну) and multi-select actions.
 */
export function ShelfLogoChip({
  title,
  icon,
  onPress,
  danger,
  accessibilityLabel,
  style,
}: Props) {
  const iconSize = s(18);
  const iconColor = danger ? colors.stamp : colors.white;

  const row = (
    <View style={styles.row}>
      <Text
        style={[styles.title, danger ? styles.titleDanger : styles.titleOnGradient]}
        numberOfLines={1}
      >
        {title}
      </Text>
      <View style={[styles.iconWrap, danger && styles.iconWrapDanger]}>
        <ShelfActionGlyph name={icon} color={iconColor} size={iconSize} />
      </View>
    </View>
  );

  if (danger) {
    return (
      <Pressable
        style={({ pressed }) => [
          styles.chip,
          styles.chipDanger,
          pressed && styles.pressed,
          style,
        ]}
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel || title}
      >
        {row}
      </Pressable>
    );
  }

  return (
    <Pressable
      style={({ pressed }) => [styles.chipOuter, pressed && styles.pressed, style]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel || title}
    >
      <ImageBackground
        source={require("../assets/fab-gradient.png")}
        style={styles.chipBg}
        imageStyle={styles.chipBgImg}
      >
        <View style={styles.chipInner}>{row}</View>
      </ImageBackground>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chipOuter: {
    borderRadius: s(999),
    overflow: "hidden",
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.55)",
    shadowColor: "#E83E8C",
    shadowOpacity: 0.4,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 3 },
    elevation: 6,
    backgroundColor: "#E83E8C",
  },
  chipBg: { width: "100%" },
  chipBgImg: { borderRadius: s(999) },
  chipInner: {
    paddingVertical: s(8),
    paddingLeft: s(12),
    paddingRight: s(8),
  },
  chip: {
    borderRadius: s(999),
    paddingVertical: s(8),
    paddingLeft: s(12),
    paddingRight: s(8),
  },
  chipDanger: {
    borderWidth: 2,
    borderColor: colors.stamp,
    backgroundColor: "#FFF5F3",
  },
  pressed: {
    opacity: 0.9,
    transform: [{ scale: 0.97 }],
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: s(8),
  },
  title: {
    flexShrink: 1,
    fontWeight: "800",
    fontSize: fs(13),
  },
  titleOnGradient: {
    color: colors.white,
    textShadowColor: "rgba(0,0,0,0.25)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 1,
  },
  titleDanger: {
    color: colors.stamp,
  },
  iconWrap: {
    width: s(26),
    height: s(26),
    borderRadius: s(13),
    backgroundColor: "rgba(0,0,0,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  iconWrapDanger: {
    backgroundColor: "rgba(194,59,34,0.12)",
  },
});
