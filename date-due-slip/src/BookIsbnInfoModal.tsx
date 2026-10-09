import type { ReactNode } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { BookCover } from "./BookCover";
import { htmlToPlain } from "./htmlText";
import { colors, fs, s } from "./theme";
import type { Book } from "./types";

type Props = {
  book: Book | null;
  visible: boolean;
  onClose: () => void;
  /** Optional footer action (e.g. link to all copies). */
  footer?: ReactNode;
};

function isbnMetaRows(book: Book): [string, string][] {
  return (
    [
      ["Повна назва", book.title_long && book.title_long !== book.title ? book.title_long : ""],
      ["Видавець", book.publisher],
      ["Дата видання", book.publish_date],
      ["Палітурка", book.binding || ""],
      ["Мова", book.language || ""],
      ["Видання", book.edition || ""],
      ["Сторінок", book.pages != null ? String(book.pages) : ""],
      ["Розміри", book.dimensions || ""],
      ["MSRP", book.msrp || ""],
      [
        "Теми",
        (book.subjects || []).length ? (book.subjects || []).join(", ") : "",
      ],
      [
        "Dewey",
        (book.dewey_decimal || []).length
          ? (book.dewey_decimal || []).join(", ")
          : "",
      ],
      ["Джерело", book.catalog_source || ""],
      ["Вік", book.reader_age_summary || ""],
    ] as [string, string][]
  ).filter(([, v]) => !!(v && String(v).trim()));
}

/**
 * My Library–style book info sheet (ISBN details) — shared by shelf / copy / book history.
 */
export function BookIsbnInfoModal({ book, visible, onClose, footer }: Props) {
  if (!book) return null;
  const rows = isbnMetaRows(book);
  const otherIsbns = (book.other_isbns || [])
    .map((o) => (o.binding ? `${o.isbn} (${o.binding})` : o.isbn))
    .join("; ");

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
          <ScrollView style={styles.scroll} nestedScrollEnabled>
            <BookCover uri={book.cover_url} size="md" />
            <Text style={styles.meta}>{book.authors || "—"}</Text>
            <Text style={styles.meta}>
              {book.isbn?.startsWith("9799") || book.isbn_missing
                ? book.note || "ISBN code not exists"
                : `ISBN ${book.isbn}${book.isbn10 ? ` · ${book.isbn10}` : ""}`}
            </Text>
            <Text style={styles.section}>Дані ISBN</Text>
            {rows.map(([k, v]) => (
              <Text key={k} style={styles.meta}>
                <Text style={styles.metaBold}>{k}: </Text>
                {v}
              </Text>
            ))}
            {otherIsbns ? (
              <Text style={styles.meta}>
                <Text style={styles.metaBold}>Інші ISBN: </Text>
                {otherIsbns}
              </Text>
            ) : null}
            {book.synopsis || book.overview ? (
              <View style={styles.proseWrap}>
                <Text style={[styles.meta, styles.metaBold, { marginBottom: 4 }]}>
                  {book.synopsis ? "Синопсис" : "Огляд"}
                </Text>
                <ScrollView style={styles.proseScroll} nestedScrollEnabled>
                  <Text style={styles.meta}>
                    {htmlToPlain(book.synopsis || book.overview)}
                  </Text>
                </ScrollView>
              </View>
            ) : null}
            {book.excerpt ? (
              <View style={styles.proseWrap}>
                <Text style={[styles.meta, styles.metaBold, { marginBottom: 4 }]}>
                  Уривок
                </Text>
                <ScrollView style={styles.proseScroll} nestedScrollEnabled>
                  <Text style={styles.meta}>{htmlToPlain(book.excerpt)}</Text>
                </ScrollView>
              </View>
            ) : null}
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
    paddingBottom: 24,
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
  scroll: { paddingHorizontal: 16, paddingTop: 12 },
  meta: { color: colors.muted, marginTop: 4, fontSize: fs(14) },
  metaBold: { fontWeight: "700", color: colors.ink },
  section: {
    marginTop: 14,
    marginBottom: 4,
    fontWeight: "800",
    color: colors.ink,
    fontSize: fs(15),
  },
  proseWrap: { marginTop: 12 },
  proseScroll: { maxHeight: s(160) },
});
