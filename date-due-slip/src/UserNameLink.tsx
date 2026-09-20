import { type ReactNode } from "react";
import { Pressable, StyleSheet, Text, type StyleProp, type TextStyle } from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "./auth";
import { colors } from "./theme";

type MiniUser = { id: number; username: string };

type Props = {
  user: MiniUser | null | undefined;
  style?: StyleProp<TextStyle>;
  children?: ReactNode;
};

/**
 * Own username → account profile (Ще/Профіль).
 * Other username → their owned book copies (/user/:id).
 */
export function UserNameLink({ user, style, children }: Props) {
  const router = useRouter();
  const { user: me } = useAuth();
  if (!user) return null;

  const label = children ?? user.username;
  const go = () => {
    if (me && user.id === me.id) {
      router.push("/(tabs)/more");
    } else {
      router.push(`/user/${user.id}`);
    }
  };

  return (
    <Pressable onPress={go} hitSlop={4} accessibilityRole="link">
      <Text style={[styles.link, style]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  link: { color: colors.stamp, fontWeight: "700" },
});
