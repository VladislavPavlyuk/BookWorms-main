import { useCallback, useEffect, useState } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { CameraView, useCameraPermissions, type BarcodeScanningResult } from "expo-camera";
import { colors, fs, s, btnRadius } from "./theme";

/** Digits only; keep 10 or 13 for ISBN-10 / EAN-13 (978/979). */
export function normalizeIsbn(raw: string): string | null {
  const digits = (raw || "").replace(/[^0-9Xx]/g, "").toUpperCase();
  if (digits.length === 13 && /^\d{13}$/.test(digits)) return digits;
  if (digits.length === 10 && /^[\dX]{10}$/.test(digits)) return digits;
  if (digits.length > 13) {
    const tail13 = digits.slice(-13);
    if (/^\d{13}$/.test(tail13)) return tail13;
  }
  return null;
}

type Props = {
  visible: boolean;
  onClose: () => void;
  /** Called once with a normalized ISBN when a barcode is recognized. */
  onScan: (isbn: string) => void;
};

/**
 * Full-screen camera barcode scanner for ISBN / EAN-13 on book covers.
 */
export function IsbnScanModal({ visible, onClose, onScan }: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [hint, setHint] = useState("Наведіть на штрихкод ISBN");

  useEffect(() => {
    if (!visible) {
      setScanned(false);
      setHint("Наведіть на штрихкод ISBN");
      return;
    }
    if (permission && !permission.granted && permission.canAskAgain) {
      requestPermission();
    }
  }, [visible, permission, requestPermission]);

  const onBarcode = useCallback(
    (result: BarcodeScanningResult) => {
      if (scanned || !visible) return;
      const isbn = normalizeIsbn(result.data);
      if (!isbn) {
        setHint("Не схоже на ISBN — спробуйте ще");
        return;
      }
      setScanned(true);
      setHint(isbn);
      onScan(isbn);
    },
    [onScan, scanned, visible]
  );

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.root}>
        {!permission ? (
          <Text style={styles.center}>…</Text>
        ) : !permission.granted ? (
          <View style={styles.perm}>
            <Text style={styles.permText}>
              Потрібен доступ до камери, щоб сканувати ISBN на обкладинці.
            </Text>
            <Pressable style={styles.btn} onPress={requestPermission}>
              <Text style={styles.btnText}>Дозволити камеру</Text>
            </Pressable>
            <Pressable onPress={onClose}>
              <Text style={styles.link}>Скасувати</Text>
            </Pressable>
          </View>
        ) : (
          <>
            <CameraView
              style={StyleSheet.absoluteFill}
              facing="back"
              barcodeScannerSettings={{
                barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e", "code128", "code39"],
              }}
              onBarcodeScanned={scanned ? undefined : onBarcode}
            />
            <View style={styles.overlay} pointerEvents="box-none">
              <View style={styles.frame} />
              <Text style={styles.hint}>{hint}</Text>
              <Pressable style={styles.close} onPress={onClose}>
                <Text style={styles.closeText}>Закрити</Text>
              </Pressable>
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
  permText: { color: colors.ink, fontSize: fs(16), lineHeight: fs(22), textAlign: "center" },
  btn: {
    backgroundColor: colors.ink,
    padding: s(14),
    borderRadius: btnRadius,
    alignSelf: "center",
    minWidth: s(200),
  },
  btnText: { color: colors.white, textAlign: "center", fontWeight: "700", fontSize: fs(16) },
  link: { color: colors.stamp, textAlign: "center", fontWeight: "700", fontSize: fs(15) },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "center",
    alignItems: "center",
    paddingBottom: s(48),
  },
  frame: {
    width: "72%",
    aspectRatio: 1.6,
    borderWidth: 2,
    borderColor: "rgba(255,251,243,0.9)",
    borderRadius: 12,
    backgroundColor: "transparent",
  },
  hint: {
    marginTop: s(20),
    color: "#fff",
    fontWeight: "700",
    fontSize: fs(15),
    textAlign: "center",
    paddingHorizontal: s(16),
    textShadowColor: "#000",
    textShadowRadius: 4,
  },
  close: {
    position: "absolute",
    bottom: s(40),
    backgroundColor: colors.ink,
    paddingHorizontal: s(24),
    paddingVertical: s(12),
    borderRadius: btnRadius,
  },
  closeText: { color: colors.white, fontWeight: "800", fontSize: fs(16) },
});
