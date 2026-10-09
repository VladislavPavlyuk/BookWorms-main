import { Pressable, StyleSheet, Text, View } from "react-native";
import { ShelfActionGlyph } from "./ShelfActionGlyphs";
import { colors, fs, s } from "./theme";

type CheckProps = {
  label: string;
  checked: boolean;
  onPress: () => void;
};

/** Classic square select-box row — same language as My Library cover checkboxes. */
export function ShelfCheckRow({ label, checked, onPress }: CheckProps) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
    >
      <View style={[styles.box, checked && styles.boxOn]}>
        {checked ? (
          <ShelfActionGlyph name="check" color={colors.white} size={s(18)} />
        ) : null}
      </View>
      <Text style={[styles.label, checked && styles.labelOn]}>{label}</Text>
    </Pressable>
  );
}

type RadioProps = {
  label: string;
  selected: boolean;
  onPress: () => void;
};

/** Classic radio row for mutually exclusive options. */
export function ShelfRadioRow({ label, selected, onPress }: RadioProps) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
      accessibilityRole="radio"
      accessibilityState={{ selected }}
    >
      <View style={[styles.radio, selected && styles.radioOn]}>
        {selected ? <View style={styles.radioDot} /> : null}
      </View>
      <Text style={[styles.label, selected && styles.labelOn]}>{label}</Text>
    </Pressable>
  );
}

const BOX = s(36);

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: s(12),
    paddingVertical: s(10),
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
  },
  rowPressed: {
    opacity: 0.85,
  },
  box: {
    width: BOX,
    height: BOX,
    borderRadius: s(8),
    borderWidth: 2.5,
    borderColor: "rgba(42,31,20,0.45)",
    backgroundColor: "rgba(255,255,255,0.96)",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOpacity: 0.12,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 3,
  },
  boxOn: {
    backgroundColor: colors.stamp,
    borderColor: colors.stamp,
  },
  radio: {
    width: BOX,
    height: BOX,
    borderRadius: BOX / 2,
    borderWidth: 2.5,
    borderColor: "rgba(42,31,20,0.45)",
    backgroundColor: "rgba(255,255,255,0.96)",
    alignItems: "center",
    justifyContent: "center",
  },
  radioOn: {
    borderColor: colors.stamp,
  },
  radioDot: {
    width: BOX * 0.42,
    height: BOX * 0.42,
    borderRadius: BOX * 0.21,
    backgroundColor: colors.stamp,
  },
  label: {
    flex: 1,
    color: colors.ink,
    fontSize: fs(15),
    fontWeight: "500",
  },
  labelOn: {
    fontWeight: "800",
  },
});
