import { StyleSheet, View } from "react-native";
import { colors } from "./theme";

/** Classic ☰ — three bars, no icon font. */
export function BurgerGlyph({
  color = colors.ink,
  size = 20,
}: {
  color?: string;
  size?: number;
}) {
  const barH = Math.max(2, Math.round(size * 0.12));
  return (
    <View style={{ width: size, height: size * 0.72, justifyContent: "space-between" }}>
      <View style={[styles.bar, { height: barH, backgroundColor: color }]} />
      <View style={[styles.bar, { height: barH, backgroundColor: color }]} />
      <View style={[styles.bar, { height: barH, backgroundColor: color }]} />
    </View>
  );
}

/** Classic bell silhouette — no icon font. */
export function BellGlyph({
  color = colors.ink,
  size = 20,
}: {
  color?: string;
  size?: number;
}) {
  const s = size;
  return (
    <View style={{ width: s, height: s, alignItems: "center", justifyContent: "flex-end" }}>
      {/* crown */}
      <View
        style={{
          width: s * 0.18,
          height: s * 0.12,
          borderRadius: s * 0.09,
          backgroundColor: color,
          marginBottom: -1,
        }}
      />
      {/* dome */}
      <View
        style={{
          width: s * 0.55,
          height: s * 0.32,
          borderTopLeftRadius: s * 0.28,
          borderTopRightRadius: s * 0.28,
          backgroundColor: color,
        }}
      />
      {/* body flare */}
      <View
        style={{
          width: s * 0.78,
          height: s * 0.28,
          borderBottomLeftRadius: s * 0.08,
          borderBottomRightRadius: s * 0.08,
          backgroundColor: color,
          marginTop: -1,
        }}
      />
      {/* clapper */}
      <View
        style={{
          width: s * 0.2,
          height: s * 0.14,
          borderRadius: s * 0.1,
          backgroundColor: color,
          marginTop: 1,
        }}
      />
    </View>
  );
}

/** Close ✕ for menu panel. */
export function CloseGlyph({
  color = colors.ink,
  size = 18,
}: {
  color?: string;
  size?: number;
}) {
  const t = Math.max(2, Math.round(size * 0.12));
  const len = size * 0.85;
  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          position: "absolute",
          width: len,
          height: t,
          backgroundColor: color,
          borderRadius: t,
          transform: [{ rotate: "45deg" }],
        }}
      />
      <View
        style={{
          position: "absolute",
          width: len,
          height: t,
          backgroundColor: color,
          borderRadius: t,
          transform: [{ rotate: "-45deg" }],
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    width: "100%",
    borderRadius: 1,
  },
});
