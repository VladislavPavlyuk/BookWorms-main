import { useEffect, useRef, useState } from "react";
import {
  Animated,
  ImageBackground,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import {
  isNotifySoundEnabled,
  setNotifySoundEnabled,
} from "../src/notifySound";
import { ShelfActionGlyph } from "../src/ShelfActionGlyphs";
import { colors, fs, s } from "../src/theme";

function SoundWavesGlyph({
  on,
  color,
  size = 22,
}: {
  on: boolean;
  color: string;
  size?: number;
}) {
  const t = Math.max(2, size * 0.12);
  return (
    <View style={{ width: size, height: size, justifyContent: "center", alignItems: "flex-start" }}>
      <View
        style={{
          width: size * 0.28,
          height: size * 0.38,
          borderRadius: t,
          backgroundColor: color,
          marginLeft: size * 0.08,
        }}
      />
      <View
        style={{
          position: "absolute",
          left: size * 0.28,
          width: 0,
          height: 0,
          borderTopWidth: size * 0.22,
          borderBottomWidth: size * 0.22,
          borderLeftWidth: size * 0.28,
          borderTopColor: "transparent",
          borderBottomColor: "transparent",
          borderLeftColor: color,
        }}
      />
      {on ? (
        <>
          <View
            style={{
              position: "absolute",
              right: size * 0.28,
              width: size * 0.22,
              height: size * 0.22,
              borderRadius: size,
              borderWidth: t,
              borderColor: color,
              borderLeftColor: "transparent",
              borderBottomColor: "transparent",
              transform: [{ rotate: "45deg" }],
            }}
          />
          <View
            style={{
              position: "absolute",
              right: size * 0.06,
              width: size * 0.38,
              height: size * 0.38,
              borderRadius: size,
              borderWidth: t,
              borderColor: color,
              borderLeftColor: "transparent",
              borderBottomColor: "transparent",
              transform: [{ rotate: "45deg" }],
            }}
          />
        </>
      ) : (
        <View
          style={{
            position: "absolute",
            right: size * 0.04,
            width: t,
            height: size * 0.55,
            borderRadius: t,
            backgroundColor: color,
            transform: [{ rotate: "28deg" }],
          }}
        />
      )}
    </View>
  );
}

function ChevronGlyph({ color, size = 14 }: { color: string; size?: number }) {
  const t = Math.max(2, size * 0.18);
  return (
    <View
      style={{
        width: size,
        height: size,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <View
        style={{
          width: size * 0.55,
          height: size * 0.55,
          borderTopWidth: t,
          borderRightWidth: t,
          borderColor: color,
          transform: [{ rotate: "45deg" }],
          marginLeft: -size * 0.12,
        }}
      />
    </View>
  );
}

type DestProps = {
  title: string;
  body: string;
  icon: "library" | "qr";
  onPress: () => void;
  accent?: "library" | "qr";
};

function DestTile({ title, body, icon, onPress }: DestProps) {
  const scale = useRef(new Animated.Value(1)).current;
  const pressIn = () =>
    Animated.spring(scale, { toValue: 0.975, useNativeDriver: true, speed: 40, bounciness: 0 }).start();
  const pressOut = () =>
    Animated.spring(scale, { toValue: 1, useNativeDriver: true, speed: 28, bounciness: 6 }).start();

  return (
    <Animated.View style={{ transform: [{ scale }], marginBottom: s(12) }}>
      <Pressable
        onPress={onPress}
        onPressIn={pressIn}
        onPressOut={pressOut}
        accessibilityRole="button"
        accessibilityLabel={title}
        style={styles.destOuter}
      >
        <View style={styles.destRail}>
          <ImageBackground
            source={require("../assets/fab-gradient.png")}
            style={StyleSheet.absoluteFill}
            imageStyle={styles.destRailImg}
          />
        </View>
        <View style={styles.destBody}>
          <View style={styles.destIconWell}>
            <ImageBackground
              source={require("../assets/fab-gradient.png")}
              style={styles.destIconBg}
              imageStyle={styles.destIconBgImg}
            >
              <ShelfActionGlyph name={icon} color={colors.white} size={s(20)} />
            </ImageBackground>
          </View>
          <View style={styles.destText}>
            <Text style={styles.destTitle}>{title}</Text>
            <Text style={styles.destBodyText} numberOfLines={3}>
              {body}
            </Text>
          </View>
          <View style={styles.destChevron}>
            <ChevronGlyph color={colors.muted} size={s(16)} />
          </View>
        </View>
      </Pressable>
    </Animated.View>
  );
}

export default function SettingsScreen() {
  const router = useRouter();
  const [soundOn, setSoundOn] = useState(true);
  const pulse = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    isNotifySoundEnabled().then(setSoundOn);
  }, []);

  const toggleSound = (v: boolean) => {
    setSoundOn(v);
    setNotifySoundEnabled(v);
    if (v) {
      pulse.setValue(0.92);
      Animated.sequence([
        Animated.spring(pulse, { toValue: 1.06, useNativeDriver: true, friction: 4 }),
        Animated.spring(pulse, { toValue: 1, useNativeDriver: true, friction: 5 }),
      ]).start();
    }
  };

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <Text style={styles.pageTitle}>Налаштування</Text>

      <Text style={styles.sectionLabel}>Сповіщення</Text>
      <Animated.View style={[styles.soundCard, { transform: [{ scale: pulse }] }]}>
        {soundOn ? (
          <ImageBackground
            source={require("../assets/fab-gradient.png")}
            style={styles.soundOnBg}
            imageStyle={styles.soundOnBgImg}
          >
            <View style={styles.soundRow}>
              <View style={styles.soundGlyphOn}>
                <SoundWavesGlyph on color={colors.white} size={s(26)} />
              </View>
              <View style={styles.soundText}>
                <Text style={styles.soundTitleOn}>Звук сповіщень</Text>
                <Text style={styles.soundBodyOn}>
                  Вібрація при нових непрочитаних
                </Text>
              </View>
              <Switch
                value={soundOn}
                onValueChange={toggleSound}
                trackColor={{ false: "rgba(255,255,255,0.35)", true: "rgba(255,255,255,0.55)" }}
                thumbColor={colors.white}
                ios_backgroundColor="rgba(255,255,255,0.35)"
              />
            </View>
          </ImageBackground>
        ) : (
          <View style={styles.soundOffBg}>
            <View style={styles.soundRow}>
              <View style={styles.soundGlyphOff}>
                <SoundWavesGlyph on={false} color={colors.muted} size={s(26)} />
              </View>
              <View style={styles.soundText}>
                <Text style={styles.soundTitleOff}>Звук сповіщень</Text>
                <Text style={styles.soundBodyOff}>Вимкнено — тихий режим</Text>
              </View>
              <Switch
                value={soundOn}
                onValueChange={toggleSound}
                trackColor={{ false: colors.line, true: colors.stampOk }}
                thumbColor={colors.white}
              />
            </View>
          </View>
        )}
      </Animated.View>

      <Text style={styles.sectionLabel}>Сервіси</Text>
      <DestTile
        title="Спільна бібліотека"
        body="Об’єднання полиць, код merge, голосування за адміна, поділ примірників."
        icon="library"
        onPress={() => router.push("/library")}
      />
      <DestTile
        title="Друкувати QR коди"
        body="Унікальні QR 20×20 мм для примірників. Точний A4 — у веб-версії Налаштування."
        icon="qr"
        onPress={() => router.push("/qr-print?from=settings")}
      />

      <Pressable
        onPress={() => router.back()}
        style={({ pressed }) => [styles.backBtn, pressed && styles.backPressed]}
        accessibilityRole="button"
        accessibilityLabel="Назад"
      >
        <Text style={styles.backChevron}>‹</Text>
        <Text style={styles.backText}>Назад</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.screen },
  content: {
    paddingHorizontal: s(16),
    paddingTop: s(12),
    paddingBottom: s(40),
  },

  pageTitle: {
    color: colors.ink,
    fontSize: fs(22),
    fontWeight: "800",
    marginBottom: s(18),
    marginLeft: s(4),
  },

  sectionLabel: {
    color: colors.muted,
    fontSize: fs(12),
    fontWeight: "800",
    letterSpacing: 1.1,
    textTransform: "uppercase",
    marginBottom: s(10),
    marginLeft: s(4),
  },

  soundCard: {
    borderRadius: s(20),
    overflow: "hidden",
    marginBottom: s(22),
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.45)",
  },
  soundOnBg: { width: "100%" },
  soundOnBgImg: { borderRadius: s(18) },
  soundOffBg: {
    backgroundColor: colors.paper,
    borderRadius: s(18),
    borderWidth: 1,
    borderColor: colors.line,
  },
  soundRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: s(12),
    paddingVertical: s(16),
    paddingHorizontal: s(14),
  },
  soundGlyphOn: {
    width: s(48),
    height: s(48),
    borderRadius: s(16),
    backgroundColor: "rgba(0,0,0,0.2)",
    alignItems: "center",
    justifyContent: "center",
  },
  soundGlyphOff: {
    width: s(48),
    height: s(48),
    borderRadius: s(16),
    backgroundColor: colors.paperDark,
    alignItems: "center",
    justifyContent: "center",
  },
  soundText: { flex: 1, minWidth: 0 },
  soundTitleOn: {
    color: colors.white,
    fontWeight: "900",
    fontSize: fs(16),
    textShadowColor: "rgba(0,0,0,0.25)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 1,
  },
  soundBodyOn: {
    color: "rgba(255,251,243,0.9)",
    fontSize: fs(12),
    marginTop: 3,
    lineHeight: fs(16),
  },
  soundTitleOff: {
    color: colors.ink,
    fontWeight: "800",
    fontSize: fs(16),
  },
  soundBodyOff: {
    color: colors.muted,
    fontSize: fs(12),
    marginTop: 3,
    lineHeight: fs(16),
  },

  destOuter: {
    flexDirection: "row",
    backgroundColor: colors.paper,
    borderRadius: s(18),
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.line,
    minHeight: s(88),
  },
  destRail: {
    width: s(7),
    overflow: "hidden",
  },
  destRailImg: {},
  destBody: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: s(12),
    paddingVertical: s(14),
    paddingHorizontal: s(12),
  },
  destIconWell: {
    borderRadius: s(14),
    overflow: "hidden",
    borderWidth: 1.5,
    borderColor: "rgba(255,255,255,0.5)",
  },
  destIconBg: {
    width: s(44),
    height: s(44),
    alignItems: "center",
    justifyContent: "center",
  },
  destIconBgImg: { borderRadius: s(12) },
  destText: { flex: 1, minWidth: 0 },
  destTitle: {
    color: colors.ink,
    fontWeight: "900",
    fontSize: fs(16),
    marginBottom: 4,
  },
  destBodyText: {
    color: colors.muted,
    fontSize: fs(12),
    lineHeight: fs(17),
  },
  destChevron: {
    width: s(28),
    height: s(28),
    borderRadius: s(14),
    backgroundColor: colors.paperDark,
    alignItems: "center",
    justifyContent: "center",
  },

  backBtn: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: s(2),
    marginTop: s(8),
    paddingVertical: s(10),
    paddingHorizontal: s(4),
  },
  backPressed: { opacity: 0.7 },
  backChevron: {
    color: colors.stamp,
    fontSize: fs(28),
    fontWeight: "300",
    lineHeight: s(28),
    marginTop: -2,
  },
  backText: {
    color: colors.stamp,
    fontWeight: "800",
    fontSize: fs(15),
  },
});
