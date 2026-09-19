import { ImageBackground, StyleSheet, View, type ReactNode } from "react-native";

const BG = require("../assets/bg-portrait.jpg");

/** Fixed date-due-slip photo behind every screen. */
export function SiteBackground({ children }: { children: ReactNode }) {
  return (
    <View style={styles.root}>
      <ImageBackground source={BG} style={styles.bg} resizeMode="cover">
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
