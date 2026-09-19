import { Platform, Vibration } from "react-native";

/** Mobile notify cue (vibration). Web uses /static/sounds/notify.wav. */
export async function playNotifySound() {
  try {
    if (Platform.OS === "android") {
      Vibration.vibrate([0, 70, 40, 90]);
    } else {
      Vibration.vibrate(80);
    }
  } catch {
    /* ignore */
  }
}
