import { useCallback, useEffect, useRef, useState } from "react";
import {
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImageManipulator from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import { Audio } from "expo-av";
import { ShelfLogoChip } from "./ShelfLogoChip";
import { colors, fs, s, btnRadius } from "./theme";

const MAX = 8;
const AUTO_DELAY_MS = 2800;
const READY_GRACE_MS = 600;
const GUIDE_W = 0.64;
const GUIDE_H = 0.88;

type Photo = { uri: string; name: string; type: string };

type Props = {
  visible: boolean;
  onClose: () => void;
  onCaptured: (photo: Photo) => void;
  count: number;
};

async function playShutter() {
  try {
    await Audio.setAudioModeAsync({
      playsInSilentModeIOS: true,
      staysActiveInBackground: false,
    });
    const { sound } = await Audio.Sound.createAsync(
      require("../assets/shutter_click.wav"),
      { shouldPlay: true, volume: 1 }
    );
    sound.setOnPlaybackStatusUpdate((st) => {
      if (st.isLoaded && st.didJustFinish) sound.unloadAsync().catch(() => {});
    });
  } catch {
    /* ignore */
  }
}

async function cropBookOnly(uri: string): Promise<string> {
  try {
    const meta = await ImageManipulator.manipulateAsync(uri, [], {
      format: ImageManipulator.SaveFormat.JPEG,
    });
    const w = meta.width || 0;
    const h = meta.height || 0;
    if (w < 32 || h < 32) return uri;

    const cropW = Math.max(32, Math.floor(w * GUIDE_W));
    const cropH = Math.max(32, Math.floor(h * GUIDE_H));
    const originX = Math.max(0, Math.floor((w - cropW) / 2));
    const originY = Math.max(0, Math.floor((h - cropH) / 2));
    const width = Math.min(cropW, w - originX);
    const height = Math.min(cropH, h - originY);
    if (width < 32 || height < 32) return uri;

    const cropped = await ImageManipulator.manipulateAsync(
      uri,
      [{ crop: { originX, originY, width, height } }],
      { compress: 0.9, format: ImageManipulator.SaveFormat.JPEG }
    );
    return cropped.uri || uri;
  } catch (e) {
    console.warn("[BookCoverCapture] crop failed", e);
    return uri;
  }
}

/** Native camera intent — works when CameraView.takePicture is dead (Android Modal). */
async function captureViaImagePicker(): Promise<string> {
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) {
    throw new Error("Немає дозволу камери");
  }
  const result = await ImagePicker.launchCameraAsync({
    mediaTypes: ["images"],
    quality: 0.85,
    exif: false,
    allowsEditing: false,
    cameraType: ImagePicker.CameraType.back,
  });
  if (result.canceled || !result.assets?.[0]?.uri) {
    throw new Error("Зйомку скасовано");
  }
  return result.assets[0].uri;
}

/**
 * Book cover capture.
 * - Mount CameraView ONLY while visible (one active camera — Expo rule).
 * - Prefer CameraView.takePictureAsync; fall back to ImagePicker on failure.
 */
export function BookCoverCaptureModal({ visible, onClose, onCaptured, count }: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const camRef = useRef<CameraView | null>(null);
  const [hint, setHint] = useState("Очікування камери…");
  const [busy, setBusy] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const takingRef = useRef(false);
  const readyAtRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onCapturedRef = useRef(onCaptured);
  const countRef = useRef(count);
  onCapturedRef.current = onCaptured;
  countRef.current = count;

  const clearTimers = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (tickRef.current) clearInterval(tickRef.current);
    timerRef.current = null;
    tickRef.current = null;
    setCountdown(null);
  }, []);

  const finishCapture = useCallback(async (rawUri: string) => {
    setHint("Обрізка обкладинки…");
    const croppedUri = await cropBookOnly(rawUri);
    void playShutter();
    onCapturedRef.current({
      uri: croppedUri,
      name: `book_${Date.now()}.jpg`,
      type: "image/jpeg",
    });
    setHint("Знято. Тримайте наступну в рамці — знову автозйомка.");
  }, []);

  const shoot = useCallback(async () => {
    if (takingRef.current) return;
    if (countRef.current >= MAX) {
      setHint(`Максимум ${MAX} фото`);
      return;
    }
    takingRef.current = true;
    setBusy(true);
    clearTimers();
    setHint("Зйомка…");

    try {
      let uri: string | null = null;
      const cam = camRef.current;
      const readyLongEnough = Date.now() - readyAtRef.current >= READY_GRACE_MS;

      if (cam && cameraReady && readyLongEnough) {
        try {
          // Brief pause so preview / AF settle (Android CameraX)
          await new Promise((r) => setTimeout(r, 120));
          const pic = await cam.takePictureAsync({
            quality: 0.85,
            shutterSound: false,
            skipProcessing: false,
            exif: false,
          });
          if (pic?.uri) uri = pic.uri;
          else console.warn("[BookCoverCapture] takePicture returned empty");
        } catch (e) {
          console.warn("[BookCoverCapture] takePicture failed, fallback", e);
        }
      }

      if (!uri) {
        setHint("Системна камера…");
        uri = await captureViaImagePicker();
      }

      await finishCapture(uri);
    } catch (e) {
      console.warn("[BookCoverCapture] shoot failed", e);
      setHint(
        e instanceof Error
          ? `Зйомка не вдалася: ${e.message}`
          : `Зйомка не вдалася: ${String(e)}`
      );
    } finally {
      takingRef.current = false;
      setBusy(false);
    }
  }, [cameraReady, clearTimers, finishCapture]);

  useEffect(() => {
    if (!visible) {
      clearTimers();
      setBusy(false);
      setCameraReady(false);
      readyAtRef.current = 0;
      takingRef.current = false;
      camRef.current = null;
      setHint("Очікування камери…");
      return;
    }
    if (permission && !permission.granted && permission.canAskAgain) {
      requestPermission();
    }
  }, [visible, permission, requestPermission, clearTimers]);

  useEffect(() => {
    if (!visible || !permission?.granted || !cameraReady || busy || count >= MAX) {
      return;
    }

    clearTimers();
    let left = Math.ceil(AUTO_DELAY_MS / 1000);
    setCountdown(left);
    setHint(`Тримайте книгу в рамці — автозйомка ${left}с`);

    tickRef.current = setInterval(() => {
      left -= 1;
      if (left <= 0) {
        if (tickRef.current) clearInterval(tickRef.current);
        tickRef.current = null;
        setCountdown(0);
      } else {
        setCountdown(left);
        setHint(`Тримайте книгу в рамці — автозйомка ${left}с`);
      }
    }, 1000);

    timerRef.current = setTimeout(() => {
      void shoot();
    }, AUTO_DELAY_MS);

    return clearTimers;
  }, [visible, permission?.granted, cameraReady, count, busy, shoot, clearTimers]);

  const showCamera = visible && !!permission?.granted;

  return (
    <Modal
      visible={visible}
      animationType="fade"
      presentationStyle="fullScreen"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <View style={styles.root}>
        {!permission ? (
          <Text style={styles.center}>…</Text>
        ) : !permission.granted ? (
          <View style={styles.perm}>
            <Text style={styles.permText}>Потрібен доступ до камери для фото обкладинки.</Text>
            <ShelfLogoChip
              title="Дозволити"
              icon="qr"
              style={{ marginBottom: 12 }}
              onPress={requestPermission}
            />
            <ShelfLogoChip title="Скасувати" icon="close" onPress={onClose} />
          </View>
        ) : (
          <>
            {/* Unmount when hidden — Expo allows only one active camera preview */}
            {showCamera ? (
              <CameraView
                ref={(r) => {
                  camRef.current = r;
                }}
                style={StyleSheet.absoluteFill}
                facing="back"
                mode="picture"
                animateShutter={false}
                active={visible}
                onCameraReady={() => {
                  readyAtRef.current = Date.now();
                  setCameraReady(true);
                  setHint("Камера готова — наведіть обкладинку в рамку");
                }}
                onMountError={(err) => {
                  const message = err?.message || String(err);
                  console.warn("[BookCoverCapture] mount error", message);
                  setHint(`Камера: ${message}. Спробуйте «Зняти» (системна).`);
                  setCameraReady(false);
                }}
              />
            ) : null}
            <View style={styles.overlay} pointerEvents="box-none">
              <View style={styles.guide} />
              <Text style={styles.hint}>
                {hint}
                {countdown != null && countdown > 0 ? ` (${countdown})` : ""}
              </Text>
              <Text style={styles.meta}>
                {count} / {MAX} · автообрізка до рамки
                {Platform.OS === "android" ? " · Android" : ""}
              </Text>
              <View style={styles.row}>
                <Pressable style={styles.close} onPress={onClose} disabled={busy}>
                  <Text style={styles.closeText}>Закрити</Text>
                </Pressable>
                <Pressable
                  style={[styles.shutter, busy && { opacity: 0.5 }]}
                  onPress={() => void shoot()}
                  disabled={busy}
                  accessibilityLabel="Зняти зараз"
                >
                  <Text style={styles.closeText}>Зняти</Text>
                </Pressable>
              </View>
            </View>
          </>
        )}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#000" },
  center: { color: "#fff", textAlign: "center", marginTop: 80 },
  perm: {
    flex: 1,
    justifyContent: "center",
    padding: s(24),
    backgroundColor: colors.paper,
    gap: s(16),
  },
  permText: { color: colors.ink, fontSize: fs(16), textAlign: "center" },
  btn: {
    backgroundColor: colors.ink,
    padding: s(14),
    borderRadius: btnRadius,
    alignSelf: "center",
    minWidth: s(180),
  },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700" },
  link: { color: colors.stamp, textAlign: "center", fontWeight: "700" },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "center",
    alignItems: "center",
    paddingBottom: s(40),
  },
  guide: {
    width: "64%",
    aspectRatio: 2 / 3,
    maxHeight: "72%",
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.95)",
    borderRadius: 4,
    backgroundColor: "transparent",
  },
  hint: {
    marginTop: s(16),
    color: "#fff",
    fontWeight: "700",
    fontSize: fs(15),
    textAlign: "center",
    paddingHorizontal: s(16),
    textShadowColor: "#000",
    textShadowRadius: 4,
  },
  meta: {
    marginTop: s(6),
    color: "rgba(255,255,255,0.75)",
    fontSize: fs(12),
  },
  row: {
    position: "absolute",
    bottom: s(36),
    left: s(16),
    right: s(16),
    flexDirection: "row",
    justifyContent: "space-between",
    gap: s(12),
  },
  close: {
    backgroundColor: colors.ink,
    paddingHorizontal: s(20),
    paddingVertical: s(12),
    borderRadius: btnRadius,
  },
  shutter: {
    backgroundColor: colors.fab,
    paddingHorizontal: s(24),
    paddingVertical: s(12),
    borderRadius: btnRadius,
  },
  closeText: { color: colors.white, fontWeight: "800", fontSize: fs(16) },
});
