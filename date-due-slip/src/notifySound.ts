import * as SecureStore from "expo-secure-store";
import { Platform, Vibration } from "react-native";

/** Same key as web localStorage (`dds_notif_sound`). Default: on. */
export const NOTIF_SOUND_KEY = "dds_notif_sound";

export async function isNotifySoundEnabled(): Promise<boolean> {
  try {
    const v = await SecureStore.getItemAsync(NOTIF_SOUND_KEY);
    return v !== "0";
  } catch {
    return true;
  }
}

export async function setNotifySoundEnabled(on: boolean): Promise<void> {
  try {
    await SecureStore.setItemAsync(NOTIF_SOUND_KEY, on ? "1" : "0");
  } catch {
    /* ignore */
  }
}

/** Mobile notify cue (vibration). Web uses /static/sounds/notify.wav. */
export async function playNotifySound() {
  if (!(await isNotifySoundEnabled())) return;
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
