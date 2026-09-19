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
  /** full = responsive cover; sm/md/lg = fixed thumbs */
  size?: "sm" | "md" | "lg" | "full";
  /** Horizontal padding of parent to cancel (portrait edge bleed). */
  bleed?: number;
  style?: StyleProp<ViewStyle>;
};

const SIZES = {
  sm: { w: 48, h: 72 },
  md: { w: 64, h: 96 },
  lg: { w: 88, h: 132 },
};

const BOOK_RATIO = 2 / 3; // width / height (portrait book)

/**
 * Portrait: width = screen, height from ratio.
 * Landscape: height capped (~58% viewport), width from ratio.
 */
export function BookCover({ uri, size = "full", bleed = 0, style }: Props) {
  const { width: winW, height: winH } = useWindowDimensions();
  const src = (uri || "").trim();
  const full = size === "full";
  const dim = full ? null : SIZES[size];
  const landscape = winW > winH;

  let boxStyle: object;
  if (full) {
    if (landscape) {
      const h = Math.round(Math.min(winH * 0.58, winH - 140));
      const w = Math.round(h * BOOK_RATIO);
      boxStyle = {
        width: w,
        height: h,
        alignSelf: "center",
        borderWidth: 0,
        borderRadius: 0,
      };
    } else {
      const w = winW;
      const h = Math.round(w / BOOK_RATIO);
      boxStyle = {
        width: w,
        height: h,
        marginLeft: -bleed,
        marginRight: -bleed,
        alignSelf: "flex-start",
        borderWidth: 0,
        borderRadius: 0,
      };
    }
  } else {
    boxStyle = { width: dim!.w, height: dim!.h };
  }

  return (
    <View style={[styles.box, boxStyle, style]}>
      {src ? (
        <Image source={{ uri: src }} style={styles.img} resizeMode="cover" />
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
