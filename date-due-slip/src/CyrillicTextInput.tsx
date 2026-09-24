import { Platform, TextInput, type TextInputProps } from "react-native";

/**
 * Multilingual text (Cyrillic etc.).
 *
 * Android notes:
 * - Never pass autoCorrect={false}: RN sets TYPE_TEXT_FLAG_NO_SUGGESTIONS and
 *   Gboard can show UK layout while inserting Latin.
 * - Force autoCorrect={true} so AUTO_CORRECT is set and NO_SUGGESTIONS is cleared.
 * - Avoid visible-password / ascii-capable keyboard types.
 *
 * Emulator (scripts/run-emulator.sh):
 * - Host PC keys → Latin only (scancodes).
 * - Cyrillic → tap soft Gboard (Ukrainian). Requires
 *   `settings put secure show_ime_with_hard_keyboard 1` or soft IME stays hidden.
 */
export function CyrillicTextInput({
  keyboardType = "default",
  autoCorrect: _ac,
  spellCheck: _sc,
  autoComplete: _autoComplete,
  textContentType: _tct,
  importantForAutofill: _ifa,
  ...rest
}: TextInputProps) {
  const kb =
    keyboardType === "visible-password" || keyboardType === "ascii-capable"
      ? "default"
      : keyboardType;

  if (Platform.OS === "android") {
    return (
      <TextInput
        {...rest}
        keyboardType={kb}
        autoCorrect
        underlineColorAndroid={rest.underlineColorAndroid ?? "transparent"}
        showSoftInputOnFocus={rest.showSoftInputOnFocus ?? true}
      />
    );
  }

  return (
    <TextInput
      {...rest}
      keyboardType={kb}
      autoCorrect={_ac}
      spellCheck={_sc}
      autoComplete={_autoComplete}
      textContentType={_tct}
      importantForAutofill={_ifa}
      underlineColorAndroid={rest.underlineColorAndroid ?? "transparent"}
    />
  );
}
