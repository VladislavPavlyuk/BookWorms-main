import { useState } from "react";
import {
  Pressable,
  StyleSheet,
  TextInput,
  View,
  type TextInputProps,
} from "react-native";
import { EyeGlyph, EyeOffGlyph } from "./HeaderGlyphs";
import { colors } from "./theme";

/** Пароль + класичний eye-switch (без icon font). */
export function PasswordField({
  style,
  ...props
}: TextInputProps & { style?: TextInputProps["style"] }) {
  const [visible, setVisible] = useState(false);
  return (
    <View style={styles.wrap}>
      <TextInput
        {...props}
        style={[styles.input, style]}
        secureTextEntry={!visible}
        autoCapitalize="none"
        autoCorrect={false}
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
          <EyeOffGlyph color={colors.muted} size={22} />
        ) : (
          <EyeGlyph color={colors.muted} size={22} />
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
    marginBottom: 16,
  },
  input: {
    flex: 1,
    minWidth: 0,
    color: colors.ink,
    paddingVertical: 10,
    paddingRight: 8,
    fontSize: 16,
    borderBottomWidth: 0,
    marginBottom: 0,
  },
  toggle: {
    width: 40,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
});
