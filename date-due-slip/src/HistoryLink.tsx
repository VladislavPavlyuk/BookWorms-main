import { Pressable, Text, type StyleProp, type TextStyle } from "react-native";
import { useRouter } from "expo-router";
import { colors } from "./theme";

/** Link to per-copy event history (web: copy_history). */
export function HistoryLink({
  copyId,
  style,
  label = "Історія подій",
}: {
  copyId: number | null | undefined;
  style?: StyleProp<TextStyle>;
  label?: string;
}) {
  const router = useRouter();
  if (!copyId) return null;
  return (
    <Pressable onPress={() => router.push(`/copy/${copyId}`)} hitSlop={6}>
      <Text style={[{ color: colors.stamp, fontWeight: "800" }, style]}>{label}</Text>
    </Pressable>
  );
}
