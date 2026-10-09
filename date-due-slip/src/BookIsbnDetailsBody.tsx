import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { htmlToPlain } from "./htmlText";
import { colors, fs } from "./theme";
import type { Book } from "./types";

function catalogRows(book: Book): [string, string][] {
  const isLocal = book.isbn?.startsWith("9799") || book.isbn_missing;
  return (
    [
      ["Повна назва", book.title_long && book.title_long !== book.title ? book.title_long : ""],
      ["Автори", book.authors || ""],
      ...(isLocal
        ? [["ISBN", book.note || "ISBN code not exists"] as [string, string]]
        : ([
            ["ISBN-13", book.isbn || ""],
            ["ISBN-10", book.isbn10 || ""],
          ] as [string, string][])),
      ["Видавець", book.publisher || ""],
      ["Дата видання", book.publish_date || ""],
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
      ["Вік читача", book.reader_age_summary || ""],
    ] as [string, string][]
  ).filter(([, v]) => !!(v && String(v).trim()));
}

function ProseBlock({ title, html }: { title: string; html?: string | null }) {
  const plain = html ? htmlToPlain(html) : "";
  if (!plain.trim()) return null;
  return (
    <View style={styles.proseBlock}>
      <Text style={styles.proseTitle}>{title}</Text>
      <Text style={styles.proseText}>{plain}</Text>
    </View>
  );
}

/** Full ISBN bibliographic block — flows in parent ScrollView (no inner height caps). */
export function BookIsbnDetailsBody({ book }: { book: Book }) {
  const rows = catalogRows(book);
  const otherIsbns = (book.other_isbns || [])
    .map((o) => (o.binding ? `${o.isbn} (${o.binding})` : o.isbn))
    .join("; ");
  const infoUrl = (book.info_url || "").trim();

  return (
    <View style={styles.block}>
      <Text style={styles.sectionH}>Дані ISBN</Text>
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
      {infoUrl ? (
        <Pressable
          onPress={() => Linking.openURL(infoUrl).catch(() => undefined)}
          style={styles.catalogLink}
        >
          <Text style={styles.catalogLinkText}>Відкрити сторінку каталогу</Text>
        </Pressable>
      ) : null}
      <ProseBlock title="Синопсис" html={book.synopsis} />
      {!book.synopsis?.trim() ? <ProseBlock title="Огляд" html={book.overview} /> : null}
      <ProseBlock title="Уривок" html={book.excerpt} />
      <ProseBlock title="Текст з обкладинки" html={book.cover_text} />
    </View>
  );
}

const styles = StyleSheet.create({
  block: {
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  sectionH: { color: colors.ink, fontWeight: "800", fontSize: fs(15), marginBottom: 6 },
  meta: { color: colors.muted, marginTop: 4, fontSize: fs(13), lineHeight: fs(18) },
  metaBold: { fontWeight: "700", color: colors.ink },
  catalogLink: { marginTop: 10, alignSelf: "flex-start" },
  catalogLinkText: { color: colors.stamp, fontWeight: "700", fontSize: fs(13) },
  proseBlock: { marginTop: 12 },
  proseTitle: {
    color: colors.ink,
    fontWeight: "700",
    fontSize: fs(13),
    marginBottom: 4,
  },
  proseText: {
    color: colors.muted,
    fontSize: fs(13),
    lineHeight: fs(20),
  },
});
