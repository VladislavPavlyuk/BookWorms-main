import { type ReactNode } from "react";
import {
  ImageBackground,
  StyleSheet,
  useWindowDimensions,
  View,
} from "react-native";

const BG_VERTICAL = require("../assets/bg-landscape.jpg");
const BG_HORIZONTAL = require("../assets/bg-portrait.jpg");

/** Fixed date-due-slip photo behind every screen; swaps with orientation. */
export function SiteBackground({ children }: { children: ReactNode }) {
  const { width, height } = useWindowDimensions();
  const horizontal = width > height;

  return (
    <View style={styles.root}>
      <ImageBackground
        key={horizontal ? "h" : "v"}
        source={horizontal ? BG_HORIZONTAL : BG_VERTICAL}
        style={styles.bg}
        resizeMode="cover"
      >
        <View style={styles.veil} />
      </ImageBackground>
      <View style={styles.foreground}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#1a2433" },
  bg: {
    ...StyleSheet.absoluteFillObject,
  },
  veil: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(26, 36, 51, 0.28)",
  },
  foreground: { flex: 1 },
});
