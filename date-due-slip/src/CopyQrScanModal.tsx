import { useCallback, useEffect, useState } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { CameraView, useCameraPermissions, type BarcodeScanningResult } from "expo-camera";
import { ShelfLogoChip } from "./ShelfLogoChip";
import { colors, fs, s, btnRadius } from "./theme";

type Props = {
  visible: boolean;
  onClose: () => void;
  hint?: string;
  onScan: (payload: string) => void;
};

/** Scanner for book-instance QR labels (BW1.<token>). */
export function CopyQrScanModal({
  visible,
  onClose,
  hint = "Наведіть на QR-наклейку примірника",
  onScan,
}: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [status, setStatus] = useState(hint);

  useEffect(() => {
    if (!visible) {
      setScanned(false);
      setStatus(hint);
      return;
    }
    setStatus(hint);
    if (permission && !permission.granted && permission.canAskAgain) {
      requestPermission();
    }
  }, [visible, permission, requestPermission, hint]);

  const onBarcode = useCallback(
    (result: BarcodeScanningResult) => {
      if (scanned || !visible) return;
      const raw = (result.data || "").trim();
      if (!raw) return;
      setScanned(true);
      setStatus(raw);
      onScan(raw);
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
              Потрібен доступ до камери, щоб сканувати QR примірника.
            </Text>
            <ShelfLogoChip
              title="Дозволити камеру"
              icon="qr"
              style={{ marginBottom: 12 }}
              onPress={requestPermission}
            />
            <ShelfLogoChip title="Скасувати" icon="close" onPress={onClose} />
          </View>
        ) : (
          <>
            {visible ? (
              <CameraView
                style={StyleSheet.absoluteFill}
                facing="back"
                barcodeScannerSettings={{
                  barcodeTypes: ["qr"],
                }}
                onBarcodeScanned={scanned ? undefined : onBarcode}
              />
            ) : null}
            <View style={styles.overlay} pointerEvents="box-none">
              <View style={styles.frame} />
              <Text style={styles.hint}>{status}</Text>
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
    gap: 16,
  },
  permText: { color: "#fff", fontSize: fs(16), lineHeight: fs(22) },
  btn: {
    backgroundColor: colors.stamp,
    padding: 14,
    borderRadius: btnRadius,
  },
  btnText: { color: "#fff", fontWeight: "800", textAlign: "center" },
  link: { color: "#fff", textAlign: "center", marginTop: 8 },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "flex-end",
    alignItems: "center",
    paddingBottom: 48,
  },
  frame: {
    position: "absolute",
    top: "28%",
    width: 240,
    height: 240,
    borderWidth: 2,
    borderColor: "#fff",
    alignSelf: "center",
  },
  hint: {
    color: "#fff",
    backgroundColor: "rgba(0,0,0,0.55)",
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 16,
    maxWidth: "90%",
    textAlign: "center",
  },
  close: {
    backgroundColor: colors.paper,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: btnRadius,
  },
  closeText: { color: colors.ink, fontWeight: "800" },
});
