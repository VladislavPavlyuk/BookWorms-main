import { useState } from "react";
import {
  Image,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { colors, fs, s } from "./theme";

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
/** Mobile cover scale vs full bleed */
const COVER_SCALE = 0.95;

const MISSING_MSG =
  "Sorry … Book cover picture is not exist in our database";

/**
 * Portrait: width ≈ 95% screen, height from ratio, rounded corners.
 * Landscape: height capped (~58% viewport), width from ratio, then ×95%.
 */
export function BookCover({ uri, size = "full", style }: Props) {
  const { width: winW, height: winH } = useWindowDimensions();
  const src = (uri || "").trim();
  const [failed, setFailed] = useState(false);
  const full = size === "full";
  const dim = full ? null : SIZES[size];
  const landscape = winW > winH;
  const showImg = !!src && !failed;

  let boxStyle: object;
  let radius: number;
  if (full) {
    if (landscape) {
      const h = Math.round(Math.min(winH * 0.58, winH - 140) * COVER_SCALE);
      const w = Math.round(h * BOOK_RATIO);
      radius = Math.round(Math.min(w, h) * 0.12);
      boxStyle = {
        width: w,
        height: h,
        alignSelf: "center",
        borderRadius: radius,
      };
    } else {
      const w = Math.round(winW * COVER_SCALE);
      const h = Math.round(w / BOOK_RATIO);
      radius = Math.round(Math.min(w, h) * 0.12);
      boxStyle = {
        width: w,
        height: h,
        alignSelf: "center",
        borderRadius: radius,
      };
    }
  } else {
    const w = Math.round(dim!.w * COVER_SCALE);
    const h = Math.round(dim!.h * COVER_SCALE);
    radius = Math.round(Math.min(w, h) * 0.14);
    boxStyle = { width: w, height: h, borderRadius: radius };
  }

  return (
    <View style={[styles.box, boxStyle, style]}>
      {showImg ? (
        <Image
          source={{ uri: src }}
          style={[styles.img, { borderRadius: radius }]}
          resizeMode="cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <Text
          style={[styles.ph, full ? styles.phFull : styles.phThumb]}
          numberOfLines={full ? 6 : 4}
        >
          {MISSING_MSG}
        </Text>
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
  ph: {
    color: colors.muted,
    fontWeight: "600",
    textAlign: "center",
    paddingHorizontal: s(12),
  },
  phFull: {
    fontSize: fs(14),
    lineHeight: fs(20),
    paddingHorizontal: s(20),
  },
  phThumb: {
    fontSize: fs(9),
    lineHeight: fs(11),
    paddingHorizontal: 4,
  },
});
