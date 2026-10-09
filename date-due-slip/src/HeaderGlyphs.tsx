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

/** Classic funnel filter — no icon font. */
export function FilterGlyph({
  color = colors.ink,
  size = 18,
}: {
  color?: string;
  size?: number;
}) {
  const s = size;
  return (
    <View style={{ width: s, height: s, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: 0,
          height: 0,
          borderLeftWidth: s * 0.42,
          borderRightWidth: s * 0.42,
          borderTopWidth: s * 0.48,
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderTopColor: color,
        }}
      />
      <View
        style={{
          width: Math.max(2, Math.round(s * 0.18)),
          height: s * 0.32,
          backgroundColor: color,
          marginTop: -1,
        }}
      />
    </View>
  );
}

/** Classic camera — body + lens + viewfinder bump (desktop Scan FAB). */
export function CameraGlyph({
  color = colors.ink,
  size = 24,
}: {
  color?: string;
  size?: number;
}) {
  const s = size;
  const bodyW = s * 0.92;
  const bodyH = s * 0.58;
  const lens = s * 0.36;
  const bumpW = s * 0.28;
  const bumpH = s * 0.14;
  return (
    <View style={{ width: s, height: s, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: bumpW,
          height: bumpH,
          borderTopLeftRadius: bumpH * 0.4,
          borderTopRightRadius: bumpH * 0.4,
          backgroundColor: color,
          marginBottom: -1,
        }}
      />
      <View
        style={{
          width: bodyW,
          height: bodyH,
          borderRadius: s * 0.1,
          backgroundColor: color,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <View
          style={{
            width: lens,
            height: lens,
            borderRadius: lens / 2,
            borderWidth: Math.max(2, Math.round(s * 0.08)),
            borderColor: "#fff",
            backgroundColor: "transparent",
          }}
        />
      </View>
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

/** Classic eye (password visible). */
export function EyeGlyph({
  color = colors.ink,
  size = 22,
}: {
  color?: string;
  size?: number;
}) {
  const s = size;
  return (
    <View style={{ width: s, height: s * 0.65, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: s * 0.92,
          height: s * 0.55,
          borderRadius: s,
          borderWidth: Math.max(1.5, s * 0.08),
          borderColor: color,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <View
          style={{
            width: s * 0.28,
            height: s * 0.28,
            borderRadius: s * 0.14,
            backgroundColor: color,
          }}
        />
      </View>
    </View>
  );
}

/** Eye with slash (password hidden). */
export function EyeOffGlyph({
  color = colors.ink,
  size = 22,
}: {
  color?: string;
  size?: number;
}) {
  const s = size;
  const t = Math.max(1.5, s * 0.08);
  return (
    <View style={{ width: s, height: s * 0.7, alignItems: "center", justifyContent: "center" }}>
      <View
        style={{
          width: s * 0.92,
          height: s * 0.55,
          borderRadius: s,
          borderWidth: t,
          borderColor: color,
          alignItems: "center",
          justifyContent: "center",
          opacity: 0.85,
        }}
      >
        <View
          style={{
            width: s * 0.28,
            height: s * 0.28,
            borderRadius: s * 0.14,
            backgroundColor: color,
          }}
        />
      </View>
      <View
        style={{
          position: "absolute",
          width: s * 0.95,
          height: t,
          backgroundColor: color,
          borderRadius: t,
          transform: [{ rotate: "-35deg" }],
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
