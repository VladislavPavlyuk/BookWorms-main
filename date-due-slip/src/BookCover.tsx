import {
  Image,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { colors } from "./theme";

type Props = {
  uri?: string | null;
  /** full = screen-edge width; sm/md/lg = fixed thumbs */
  size?: "sm" | "md" | "lg" | "full";
  /** Horizontal padding of parent to cancel (pull image to screen edges). */
  bleed?: number;
  style?: StyleProp<ViewStyle>;
};

const SIZES = {
  sm: { w: 48, h: 72 },
  md: { w: 64, h: 96 },
  lg: { w: 88, h: 132 },
};

/** Full-bleed cover: left↔right screen edges, image fills width (cover crop). */
export function BookCover({ uri, size = "full", bleed = 0, style }: Props) {
  const { width: winW } = useWindowDimensions();
  const src = (uri || "").trim();
  const full = size === "full";
  const dim = full ? null : SIZES[size];
  const fullW = winW;
  const fullH = Math.round(winW * 1.25);

  return (
    <View
      style={[
        styles.box,
        full
          ? {
              width: fullW,
              height: fullH,
              marginLeft: -bleed,
              marginRight: -bleed,
              alignSelf: "flex-start",
              borderWidth: 0,
              borderRadius: 0,
            }
          : { width: dim!.w, height: dim!.h },
        style,
      ]}
    >
      {src ? (
        <Image
          source={{ uri: src }}
          style={styles.img}
          resizeMode={full ? "cover" : "cover"}
        />
      ) : (
        <Text style={styles.ph}>?</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    backgroundColor: colors.paperDark,
    borderWidth: 1,
    borderColor: colors.line,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  img: { width: "100%", height: "100%" },
  ph: { fontSize: 28, fontWeight: "700", color: colors.muted },
});
