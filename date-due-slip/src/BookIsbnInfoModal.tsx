import type { ReactNode } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { BookCover } from "./BookCover";
import { BookIsbnDetailsBody } from "./BookIsbnDetailsBody";
import { bookCoverFromDb } from "./mediaUrl";
import { colors, fs } from "./theme";
import type { Book } from "./types";

type Props = {
  book: Book | null;
  visible: boolean;
  onClose: () => void;
  /** Optional footer action (e.g. link to all copies). */
  footer?: ReactNode;
};

/**
 * My Library–style book info sheet (ISBN details) — shared by shelf / copy / book history.
 */
export function BookIsbnInfoModal({ book, visible, onClose, footer }: Props) {
  if (!book) return null;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <View style={styles.header}>
            <Text style={styles.title} numberOfLines={2}>
              {book.title}
            </Text>
            <Pressable onPress={onClose} hitSlop={8}>
              <Text style={styles.close}>Закрити</Text>
            </Pressable>
          </View>
          <ScrollView
            style={styles.scroll}
            contentContainerStyle={styles.scrollContent}
            nestedScrollEnabled
            showsVerticalScrollIndicator
            keyboardShouldPersistTaps="handled"
          >
            <BookCover uri={bookCoverFromDb(book)} size="md" />
            <Text style={styles.meta}>{book.authors || "—"}</Text>
            <Text style={styles.meta}>
              {book.isbn?.startsWith("9799") || book.isbn_missing
                ? book.note || "ISBN code not exists"
                : `ISBN ${book.isbn}${book.isbn10 ? ` · ${book.isbn10}` : ""}`}
            </Text>
            <BookIsbnDetailsBody book={book} />
            {footer}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "flex-end",
  },
  card: {
    backgroundColor: colors.white,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: "88%",
    width: "100%",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  title: { flex: 1, fontSize: fs(18), fontWeight: "800", color: colors.ink },
  close: { color: colors.stamp, fontWeight: "800", fontSize: fs(14) },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 24 },
  meta: { color: colors.muted, marginTop: 4, fontSize: fs(14) },
});
