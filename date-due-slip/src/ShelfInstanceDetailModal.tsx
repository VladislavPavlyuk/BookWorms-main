import type { ReactNode } from "react";
import {
  ImageBackground,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { BookCover } from "./BookCover";
import { BookIsbnDetailsBody } from "./BookIsbnDetailsBody";
import { bookCoverFromDb } from "./mediaUrl";
import { ShelfActionGlyph, type ShelfActionIcon } from "./ShelfActionGlyphs";
import { colors, fs, s } from "./theme";
import type { Book } from "./types";

type Props = {
  visible: boolean;
  book: Book | null;
  titleLine: ReactNode;
  onClose: () => void;
  onCoverPress: () => void;
  photoStrip?: ReactNode;
  /** Scrollable body (price, listing, pending return, …). */
  children?: ReactNode;
  /** Fixed footer — action buttons (logo / FAB gradient chrome). */
  footer?: ReactNode;
};

/**
 * Full-screen scrollable book instance profile (My Library detail).
 * Actions live in a pinned footer so they stay reachable while content scrolls.
 */
export function ShelfInstanceDetailModal({
  visible,
  book,
  titleLine,
  onClose,
  onCoverPress,
  photoStrip,
  children,
  footer,
}: Props) {
  if (!visible || !book) return null;

  return (
    <Modal visible animationType="slide" onRequestClose={onClose}>
      <View style={styles.root}>
        <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
          <View style={styles.topBar}>
            <Pressable onPress={onClose} hitSlop={8} style={styles.backBtn}>
              <Text style={styles.backText}>← Назад до полиці</Text>
            </Pressable>
            <Text style={styles.topTitle} numberOfLines={2}>
              {book.title}
            </Text>
          </View>
          <ScrollView
            style={styles.scroll}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator
            keyboardShouldPersistTaps="handled"
            nestedScrollEnabled
          >
            <Pressable
              onPress={onCoverPress}
              accessibilityRole="button"
              accessibilityLabel="Дані ISBN та обкладинка"
            >
              <BookCover uri={bookCoverFromDb(book)} size="full" bleed={0} />
            </Pressable>
            {photoStrip}
            <Text style={styles.title}>{book.title}</Text>
            {book.title_long && book.title_long !== book.title ? (
              <Text style={styles.meta}>{book.title_long}</Text>
            ) : null}
            <View style={styles.titleLine}>{titleLine}</View>
            <BookIsbnDetailsBody book={book} />
            {children}
          </ScrollView>
          {footer ? <View style={styles.footer}>{footer}</View> : null}
        </SafeAreaView>
      </View>
    </Modal>
  );
}

/** Logo / Create-Post FAB gradient chrome — yellow→magenta→purple. */
export function ShelfDetailActionBtn({
  title,
  subtitle,
  icon,
  onPress,
  danger,
  primary,
}: {
  title: string;
  subtitle?: string;
  /** Classic View-drawn glyph on the right (no icon font). */
  icon: ShelfActionIcon;
  onPress: () => void;
  danger?: boolean;
  primary?: boolean;
}) {
  const iconSize = s(28);
  const iconColor = danger ? colors.stamp : colors.white;

  const body = (
    <View style={styles.actionRow}>
      <View style={styles.actionTextCol}>
        <Text
          style={[
            danger ? styles.actionBtnTitle : styles.actionBtnTitleOnGradient,
            danger && styles.actionBtnTitleDanger,
          ]}
        >
          {title}
        </Text>
        {subtitle ? (
          <Text style={danger ? styles.actionBtnSubDanger : styles.actionBtnSubOnGradient}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      <View style={[styles.actionIconWrap, danger && styles.actionIconWrapDanger]}>
        <ShelfActionGlyph name={icon} color={iconColor} size={iconSize} />
      </View>
    </View>
  );

  if (danger) {
    return (
      <Pressable
        style={({ pressed }) => [
          styles.actionBtn,
          styles.actionBtnDanger,
          pressed && styles.actionBtnPressed,
        ]}
        onPress={onPress}
        accessibilityRole="button"
      >
        {body}
      </Pressable>
    );
  }

  return (
    <Pressable
      style={({ pressed }) => [
        styles.actionBtnOuter,
        primary && styles.actionBtnOuterPrimary,
        pressed && styles.actionBtnPressed,
      ]}
      onPress={onPress}
      accessibilityRole="button"
    >
      <ImageBackground
        source={require("../assets/fab-gradient.png")}
        style={styles.actionBtnBg}
        imageStyle={styles.actionBtnBgImg}
      >
        <View style={[styles.actionBtnInner, primary && styles.actionBtnInnerPrimary]}>
          {body}
        </View>
      </ImageBackground>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.screen },
  safe: { flex: 1 },
  topBar: {
    paddingHorizontal: 16,
    paddingBottom: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
    backgroundColor: colors.screen,
  },
  backBtn: { alignSelf: "flex-start", marginBottom: 4 },
  backText: { color: colors.ink, fontWeight: "700", fontSize: fs(14) },
  topTitle: {
    color: colors.muted,
    fontSize: fs(13),
    fontWeight: "600",
  },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 24,
    flexGrow: 1,
  },
  title: { color: colors.ink, fontWeight: "700", fontSize: fs(16), marginTop: 8 },
  meta: { color: colors.muted, marginTop: 4, fontSize: fs(13) },
  titleLine: { marginTop: 4 },
  footer: {
    borderTopWidth: 1,
    borderTopColor: colors.line,
    backgroundColor: colors.paper,
    paddingHorizontal: s(16),
    paddingTop: s(12),
    paddingBottom: s(10),
    maxHeight: "42%",
  },
  actionBtnOuter: {
    marginBottom: s(10),
    borderRadius: s(18),
    overflow: "hidden",
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.55)",
    shadowColor: "#E83E8C",
    shadowOpacity: 0.45,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
    backgroundColor: "#E83E8C",
  },
  actionBtnOuterPrimary: {
    shadowOpacity: 0.55,
    shadowRadius: 10,
    elevation: 10,
  },
  actionBtnBg: {
    width: "100%",
  },
  actionBtnBgImg: {
    borderRadius: s(16),
  },
  actionBtnInner: {
    paddingVertical: s(14),
    paddingHorizontal: s(16),
  },
  actionBtnInnerPrimary: {
    paddingVertical: s(16),
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: s(12),
  },
  actionTextCol: {
    flex: 1,
    minWidth: 0,
  },
  actionIconWrap: {
    width: s(36),
    height: s(36),
    borderRadius: s(18),
    backgroundColor: "rgba(0,0,0,0.18)",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  actionIconWrapDanger: {
    backgroundColor: "rgba(194,59,34,0.12)",
  },
  actionBtn: {
    borderWidth: 2,
    borderColor: colors.stamp,
    backgroundColor: "#FFF5F3",
    paddingVertical: s(14),
    paddingHorizontal: s(16),
    marginBottom: s(10),
    borderRadius: s(18),
  },
  actionBtnDanger: {
    borderColor: colors.stamp,
    backgroundColor: "#FFF5F3",
  },
  actionBtnPressed: {
    opacity: 0.9,
    transform: [{ scale: 0.985 }],
  },
  actionBtnTitleOnGradient: {
    color: colors.white,
    fontWeight: "800",
    fontSize: fs(16),
    textShadowColor: "rgba(0,0,0,0.28)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  actionBtnSubOnGradient: {
    color: "rgba(255,255,255,0.92)",
    marginTop: 4,
    fontSize: fs(13),
    fontWeight: "600",
    textShadowColor: "rgba(0,0,0,0.2)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 1,
  },
  actionBtnTitle: { color: colors.ink, fontWeight: "700", fontSize: fs(16) },
  actionBtnTitleDanger: { color: colors.stamp, fontWeight: "800" },
  actionBtnSubDanger: {
    color: colors.muted,
    marginTop: 4,
    fontSize: fs(13),
  },
});
