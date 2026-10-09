import { useCallback, useState } from "react";
import {
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect, useRouter } from "expo-router";
import { ApiError, ShelfApi, SlipApi } from "../../src/api";
import { BookCover } from "../../src/BookCover";
import { useAuth } from "../../src/auth";
import { bookCoverFromDb } from "../../src/mediaUrl";
import { ShelfLogoChip } from "../../src/ShelfLogoChip";
import { colors, fs, s } from "../../src/theme";
import { UserNameLink } from "../../src/UserNameLink";
import type { Shelf } from "../../src/types";

function Slip({
  shelf,
  role,
  onChat,
  onConfirm,
  onReturn,
}: {
  shelf: Shelf;
  role: "borrowed" | "lent";
  onChat?: () => void;
  onConfirm?: () => void;
  onReturn?: () => void;
}) {
  const router = useRouter();
  const overdue = shelf.is_overdue;
  return (
    <View
      style={[
        styles.slip,
        overdue && styles.overdue,
        shelf.return_pending && role === "lent" && styles.pending,
      ]}
    >
      <Text style={styles.library}>РЕЧЕНЕЦЬ</Text>
      <BookCover uri={bookCoverFromDb(shelf.book)} size="full" bleed={0} />
      <Text style={styles.title}>{shelf.book.title}</Text>
      <Text style={styles.meta}>{shelf.book.authors || "—"}</Text>
      <View style={styles.stampBox}>
        <Text style={[styles.stamp, overdue && { color: colors.danger }]}>
          {overdue ? "OVERDUE" : shelf.due_date ? `DUE ${shelf.due_date}` : "NO DATE"}
        </Text>
        {shelf.days_left != null && (
          <Text style={styles.days}>
            {overdue
              ? `${Math.abs(shelf.days_left)} дн. прострочено`
              : `${shelf.days_left} дн. лишилось`}
          </Text>
        )}
      </View>
      <View style={styles.footerRow}>
        {role === "borrowed" ? (
          <>
            <Text style={styles.footer}>Позичено у </Text>
            <UserNameLink user={shelf.borrowed_from} style={styles.footer} />
          </>
        ) : (
          <>
            <Text style={styles.footer}>У </Text>
            <UserNameLink user={shelf.user} style={styles.footer} />
          </>
        )}
        <Text style={styles.footer}>
          {shelf.return_pending
            ? role === "lent"
              ? " · чекає вашого підтвердження"
              : " · повернення надіслано"
            : ""}
        </Text>
      </View>
      <View style={styles.actions}>
        {shelf.copy_id ? (
          <ShelfLogoChip
            title="Історія подій"
            icon="history"
            style={styles.actionChip}
            onPress={() => router.push(`/copy/${shelf.copy_id}`)}
          />
        ) : null}
        {onChat ? (
          <ShelfLogoChip
            title={role === "borrowed" ? "Чат з власником" : "Чат з позичальником"}
            icon="chat"
            style={styles.actionChip}
            onPress={onChat}
          />
        ) : null}
        {role === "borrowed" && !shelf.return_pending && onReturn ? (
          <ShelfLogoChip
            title="Повернути власнику"
            icon="return"
            style={styles.actionChip}
            onPress={onReturn}
          />
        ) : null}
        {role === "lent" && shelf.return_pending && onConfirm ? (
          <ShelfLogoChip
            title={
              shelf.requires_qr_scan ? "Скан QR → повернуто" : "Підтвердити повернення"
            }
            icon={shelf.requires_qr_scan ? "qr" : "check"}
            style={styles.actionChip}
            onPress={onConfirm}
          />
        ) : null}
      </View>
    </View>
  );
}

export default function Slips() {
  const router = useRouter();
  const { user } = useAuth();
  const [borrowed, setBorrowed] = useState<Shelf[]>([]);
  const [lent, setLent] = useState<Shelf[]>([]);
  const [loanDays, setLoanDays] = useState(14);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    const data = await SlipApi.list();
    setBorrowed(data.borrowed);
    setLent(data.lent);
    setLoanDays(data.loan_days);
  };

  useFocusEffect(
    useCallback(() => {
      load().catch((e) =>
        Alert.alert("Slips", e instanceof ApiError ? e.message : String(e))
      );
    }, [])
  );

  const confirmReturn = async (shelf: Shelf) => {
    try {
      if (shelf.requires_qr_scan) {
        router.push(`/qr-scan?return_shelf_id=${shelf.id}`);
        return;
      }
      await ShelfApi.confirmReturn(shelf.id);
      Alert.alert("Повернення", "Підтверджено.");
      await load();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      if (/Відскануйте QR|QR-наклейк/i.test(msg)) {
        router.push(`/qr-scan?return_shelf_id=${shelf.id}`);
        return;
      }
      Alert.alert("Повернення", msg);
    }
  };

  const returnToOwner = async (shelf: Shelf) => {
    try {
      await ShelfApi.returnBook(shelf.id);
      Alert.alert("Повернення", "Запит надіслано власнику.");
      await load();
    } catch (e) {
      Alert.alert("Повернення", e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.screen }}
      contentContainerStyle={{ paddingBottom: 40 }}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={async () => {
            setRefreshing(true);
            await load();
            setRefreshing(false);
          }}
        />
      }
    >
      <Text style={styles.hint}>
        Стандартний термін позики: {loanDays} днів від прийняття запиту.
      </Text>
      <Text style={styles.sec}>Мої позики</Text>
      {borrowed.length === 0 ? (
        <Text style={styles.empty}>Немає позичених книг</Text>
      ) : (
        borrowed.map((shelf) => (
          <Slip
            key={shelf.id}
            shelf={shelf}
            role="borrowed"
            onReturn={
              !shelf.return_pending ? () => returnToOwner(shelf) : undefined
            }
            onChat={
              shelf.borrowed_from
                ? () => router.push(`/chat/${shelf.borrowed_from!.id}`)
                : undefined
            }
          />
        ))
      )}
      <Text style={styles.sec}>Видано мною</Text>
      {lent.length === 0 ? (
        <Text style={styles.empty}>Ніхто не тримає ваші книги</Text>
      ) : (
        lent.map((shelf) => (
          <Slip
            key={shelf.id}
            shelf={shelf}
            role="lent"
            onConfirm={shelf.return_pending ? () => confirmReturn(shelf) : undefined}
            onChat={
              shelf.user.id !== user?.id
                ? () => router.push(`/chat/${shelf.user.id}`)
                : undefined
            }
          />
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  hint: {
    color: colors.muted,
    marginBottom: s(16),
    fontSize: fs(13),
    paddingHorizontal: s(16),
    paddingTop: s(12),
  },
  sec: {
    color: colors.ink,
    fontWeight: "800",
    letterSpacing: 1,
    marginBottom: 8,
    marginTop: 8,
    paddingHorizontal: s(16),
    fontSize: fs(15),
  },
  empty: {
    color: colors.muted,
    marginBottom: s(16),
    paddingHorizontal: s(16),
    fontSize: fs(14),
  },
  slip: {
    borderWidth: 0,
    borderBottomWidth: 2,
    borderColor: colors.ink,
    backgroundColor: colors.white,
    padding: 0,
    paddingBottom: s(16),
    marginBottom: 0,
    borderStyle: "solid",
    overflow: "hidden",
  },
  overdue: { borderColor: colors.stamp, backgroundColor: "#FBE9E5" },
  pending: { borderColor: colors.stampOk, backgroundColor: "#E8F5E9" },
  library: {
    color: colors.stamp,
    fontWeight: "800",
    letterSpacing: 2,
    fontSize: fs(12),
    paddingHorizontal: s(16),
    paddingTop: s(12),
  },
  title: {
    color: colors.ink,
    fontSize: fs(16),
    fontWeight: "700",
    marginTop: 8,
    paddingHorizontal: s(16),
  },
  meta: {
    color: colors.muted,
    marginTop: 2,
    paddingHorizontal: s(16),
    fontSize: fs(13),
  },
  stampBox: {
    marginTop: s(12),
    alignItems: "flex-end",
    paddingHorizontal: s(16),
  },
  days: { color: colors.muted, fontSize: fs(12), marginTop: 2 },
  footerRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    marginTop: s(12),
    paddingHorizontal: s(16),
    borderTopWidth: 1,
    borderTopColor: colors.line,
    paddingTop: 8,
  },
  footer: {
    color: colors.ink,
    fontSize: fs(12),
  },
  stamp: {
    color: colors.stampOk,
    fontWeight: "900",
    fontSize: fs(18),
    letterSpacing: 1,
  },
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: s(12),
    paddingHorizontal: s(16),
  },
  actionChip: {
    flexGrow: 1,
    flexBasis: "40%",
  },
});
