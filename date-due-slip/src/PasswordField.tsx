import { useState } from "react";
import {
  Pressable,
  StyleSheet,
  View,
  type TextInputProps,
} from "react-native";
import { CyrillicTextInput } from "./CyrillicTextInput";
import { EyeGlyph, EyeOffGlyph } from "./HeaderGlyphs";
import { colors, fs, s } from "./theme";

/** Пароль + eye-switch. Cyrillic allowed (same IME rules as other fields). */
export function PasswordField({
  style,
  ...props
}: TextInputProps & { style?: TextInputProps["style"] }) {
  const [visible, setVisible] = useState(false);
  return (
    <View style={styles.wrap}>
      <CyrillicTextInput
        {...props}
        style={[styles.input, style]}
        secureTextEntry={!visible}
        autoCapitalize="none"
        keyboardType="default"
        textContentType="password"
      />
      <Pressable
        onPress={() => setVisible((v) => !v)}
        hitSlop={8}
        style={styles.toggle}
        accessibilityRole="button"
        accessibilityLabel={visible ? "Сховати пароль" : "Показати пароль"}
      >
        {visible ? (
          <EyeOffGlyph color={colors.muted} size={s(22)} />
        ) : (
          <EyeGlyph color={colors.muted} size={s(22)} />
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: 1,
    borderColor: colors.line,
    marginBottom: s(16),
  },
  input: {
    flex: 1,
    minWidth: 0,
    color: colors.ink,
    paddingVertical: s(12),
    paddingRight: s(8),
    fontSize: fs(16),
    borderBottomWidth: 0,
    marginBottom: 0,
  },
  toggle: {
    width: s(40),
    height: s(36),
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
});
